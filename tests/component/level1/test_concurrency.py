"""Level 1: независимость циклов токенов и ограниченная конкурентность.

Ключевое требование ``CLAUDE.md`` §16: если BUY одного токена полностью
завершён, его SELL не должен ждать завершения BUY других токенов.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from typing import Any

import pytest

from monik.config import Configuration, parse_configuration
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.quote import Quote
from monik.infrastructure.db import Database
from monik.infrastructure.providers.contract import QuoteRequest
from monik.infrastructure.providers.fake import FakeAdapter
from monik.services.observability import FakeClock
from tests.component.level1.conftest import arbitrage_rule, build_harness, level1_document
from tests.unit.config.conftest import VALID_ENV

WETH_ADDRESS = "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"


def two_token_document(**level1: Any) -> dict[str, Any]:
    """Конфигурация с двумя промежуточными токенами."""
    document = copy.deepcopy(level1_document())
    document["tokens"].append(
        {
            "network_id": "polygon",
            "address": WETH_ADDRESS,
            "symbol": "WETH",
            "decimals": 18,
            "rank": 3,
        }
    )
    if level1:
        document["scanner"]["level1"] = level1
    return document


def two_token_configuration(**level1: Any) -> Configuration:
    return parse_configuration(two_token_document(**level1), environ=dict(VALID_ENV)).config


class RecordingAdapter:
    """Адаптер, фиксирующий порядок вызовов и умеющий блокировать один из них."""

    def __init__(
        self,
        inner: FakeAdapter,
        order: list[str],
        *,
        block_symbol: str | None = None,
        gate: asyncio.Event | None = None,
        on_record: Callable[[str], None] | None = None,
    ) -> None:
        self._inner = inner
        self._order = order
        self._block_symbol = block_symbol
        self._gate = gate
        self._on_record = on_record
        self.in_flight = 0
        self.max_in_flight = 0

    @property
    def provider_id(self) -> ProviderId:
        return self._inner.provider_id

    @property
    def capabilities(self) -> Any:
        return self._inner.capabilities

    async def get_quote(self, request: QuoteRequest) -> Quote:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            symbol = (
                request.output_token.symbol
                if request.operation is OperationType.BUY
                else request.input_token.symbol
            )
            if (
                self._gate is not None
                and self._block_symbol == symbol
                and request.operation is OperationType.BUY
            ):
                await self._gate.wait()
            quote = await self._inner.get_quote(request)
            entry = f"{request.operation.value}:{symbol}"
            self._order.append(entry)
            if self._on_record is not None:
                self._on_record(entry)
            return quote
        finally:
            self.in_flight -= 1

    async def validate_fixed_route(self, request: QuoteRequest) -> Any:
        return await self._inner.validate_fixed_route(request)

    async def discover_capabilities(self) -> Any:
        return await self._inner.discover_capabilities()

    async def discover_fees(self, network_id: Any) -> Any:
        return await self._inner.discover_fees(network_id)

    async def health_check(self) -> Any:
        return await self._inner.health_check()

    async def aclose(self) -> None:
        await self._inner.aclose()


async def test_sell_of_one_token_does_not_wait_for_buy_of_another(
    database: Database, clock: FakeClock
) -> None:
    """SELL токена A выполняется, пока BUY токена B ещё висит."""
    gate = asyncio.Event()
    aave_sold = asyncio.Event()
    order: list[str] = []

    def watch(entry: str) -> None:
        if entry == "sell:AAVE":
            aave_sold.set()

    adapters = {
        ProviderId.ONEINCH: RecordingAdapter(
            FakeAdapter(ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")),
            order,
            block_symbol="WETH",
            gate=gate,
            on_record=watch,
        ),
        ProviderId.ZERO_X: RecordingAdapter(
            FakeAdapter(ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")),
            order,
            on_record=watch,
        ),
    }
    harness = build_harness(
        two_token_configuration(),
        database,
        clock,
        adapters=adapters,  # type: ignore[arg-type]
    )

    task = asyncio.ensure_future(harness.scanner.scan())
    try:
        await asyncio.wait_for(aave_sold.wait(), timeout=5)
        # Цикл WETH заблокирован на BUY: до SELL он не дошёл, а SELL для
        # AAVE уже выполнен — циклы токенов действительно независимы.
        assert not any(entry == "sell:WETH" for entry in order)
    finally:
        gate.set()
        result = await task

    assert result.opportunities


async def test_concurrency_is_bounded_by_configuration(
    database: Database, clock: FakeClock
) -> None:
    """Неограниченного числа одновременных задач быть не должно (``02`` §60)."""
    order: list[str] = []
    adapters = {
        ProviderId.ONEINCH: RecordingAdapter(
            FakeAdapter(ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")),
            order,
        ),
        ProviderId.ZERO_X: RecordingAdapter(
            FakeAdapter(ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")),
            order,
        ),
    }
    harness = build_harness(
        two_token_configuration(max_concurrent_requests=1),
        database,
        clock,
        adapters=adapters,  # type: ignore[arg-type]
    )

    await harness.scanner.scan()
    assert all(adapter.max_in_flight <= 1 for adapter in adapters.values())


@pytest.mark.parametrize("limit", [1, 4])
async def test_scan_is_deterministic_for_equal_inputs(
    database: Database, clock: FakeClock, limit: int
) -> None:
    """Одинаковые входные данные дают одинаковый результат (``02`` §94)."""
    configuration = two_token_configuration(
        max_concurrent_requests=limit, deduplication_window_seconds=0
    )
    first = await build_harness(configuration, database, clock).scanner.scan()
    second = await build_harness(configuration, database, clock).scanner.scan()

    assert [str(item.fingerprint) for item in first.opportunities] == [
        str(item.fingerprint) for item in second.opportunities
    ]
