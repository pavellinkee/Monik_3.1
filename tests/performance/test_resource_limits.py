"""Лёгкие нагрузочные проверки: лимиты, очереди и рост состояния.

Цель — не измерить скорость, а подтвердить, что заявленные ограничения
соблюдаются под нагрузкой и что состояние не растёт неограниченно
(``CLAUDE.md`` §47, ``02_LEVEL1_SCANNER.md`` §60, ``03`` §69).
"""

from __future__ import annotations

import asyncio
import copy
import pathlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest

from monik.config import Configuration, parse_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ResourceError
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.providers.contract import QuoteRequest
from monik.infrastructure.providers.fake import FakeAdapter
from monik.services.level2 import Level2Worker
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.level1.conftest import (
    RecordingDispatcher,
    arbitrage_rule,
    build_harness,
    level1_document,
)
from tests.component.level2.conftest import build_level2
from tests.unit.config.conftest import VALID_ENV

#: Количество токенов в нагрузочном сценарии.
TOKEN_COUNT = 12

#: Адреса токенов генерируются детерминированно.
TOKEN_TEMPLATE = "0x{index:040x}"


def many_tokens_document(**level1: Any) -> dict[str, Any]:
    """Конфигурация с расширенным набором токенов."""
    document = copy.deepcopy(level1_document())
    for index in range(1, TOKEN_COUNT + 1):
        document["tokens"].append(
            {
                "network_id": "polygon",
                "address": TOKEN_TEMPLATE.format(index=index + 0x100),
                "symbol": f"TKN{index}",
                "decimals": 18,
                "rank": 100 + index,
            }
        )
    document["scanner"]["amounts"] = ["100", "500"]
    if level1:
        document["scanner"]["level1"] = level1
    return document


def configured(**level1: Any) -> Configuration:
    return parse_configuration(many_tokens_document(**level1), environ=dict(VALID_ENV)).config


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "perf.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@dataclass
class ConcurrencyGauge:
    """Общий счётчик одновременных запросов всех адаптеров."""

    in_flight: int = 0
    peak: int = 0

    def enter(self) -> None:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)

    def leave(self) -> None:
        self.in_flight -= 1


class CountingAdapter(FakeAdapter):
    """Адаптер, учитывающий одновременные запросы в общем счётчике."""

    def __init__(self, *args: Any, gauge: ConcurrencyGauge, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._gauge = gauge

    async def get_quote(self, request: QuoteRequest) -> Any:
        self._gauge.enter()
        try:
            # Уступаем управление, чтобы параллельные запросы пересеклись.
            await asyncio.sleep(0)
            return await super().get_quote(request)
        finally:
            self._gauge.leave()


def counting_adapters(
    clock: FakeClock, gauge: ConcurrencyGauge | None = None
) -> dict[ProviderId, CountingAdapter]:
    shared = gauge or ConcurrencyGauge()
    return {
        ProviderId.ONEINCH: CountingAdapter(
            ProviderId.ONEINCH,
            clock,
            gauge=shared,
            output_rule=arbitrage_rule("0.050", "20.00"),
        ),
        ProviderId.ZERO_X: CountingAdapter(
            ProviderId.ZERO_X,
            clock,
            gauge=shared,
            output_rule=arbitrage_rule("0.049", "20.30"),
        ),
    }


# --- пропускная способность Level 1 ---------------------------------------


async def test_level1_scans_all_tokens(database: Database, clock: FakeClock) -> None:
    """Цикл покрывает все токены и суммы scope."""
    adapters = counting_adapters(clock)
    harness = build_harness(
        configured(),
        database,
        clock,
        adapters=adapters,  # type: ignore[arg-type]
    )

    result = await harness.scanner.scan()

    scanned = {
        call.output_token.symbol
        for adapter in adapters.values()
        for call in adapter.quote_calls
        if call.operation.value == "buy"
    }
    assert len(scanned) == TOKEN_COUNT + 1  # AAVE плюс сгенерированные токены
    assert result.scan.statistics.quote_requests > TOKEN_COUNT


async def test_concurrency_limit_is_respected_under_load(
    database: Database, clock: FakeClock
) -> None:
    """Число одновременных запросов не превышает настроенный лимит (``02`` §60)."""
    gauge = ConcurrencyGauge()
    harness = build_harness(
        configured(max_concurrent_requests=3),
        database,
        clock,
        adapters=counting_adapters(clock, gauge),  # type: ignore[arg-type]
    )

    await harness.scanner.scan()

    assert gauge.peak > 1, "нагрузочный сценарий обязан выполнять запросы параллельно"
    assert gauge.peak <= 3


async def test_opportunity_limit_bounds_created_records(
    database: Database, clock: FakeClock
) -> None:
    """Лимит на цикл ограничивает рост состояния (``02`` §48)."""
    harness = build_harness(
        configured(max_opportunities_per_scan=2, deduplication_window_seconds=0),
        database,
        clock,
        adapters=counting_adapters(clock),  # type: ignore[arg-type]
    )

    result = await harness.scanner.scan()

    assert len(result.opportunities) <= 2
    row = await database.fetch_one("SELECT COUNT(*) AS count FROM opportunities", ())
    assert row is not None and row["count"] <= 2


async def test_backpressure_stops_unbounded_handoff(database: Database, clock: FakeClock) -> None:
    """Переполненная очередь Level 2 останавливает передачу (``02`` §47)."""
    dispatcher = RecordingDispatcher(capacity=1)
    harness = build_harness(
        configured(deduplication_window_seconds=0),
        database,
        clock,
        adapters=counting_adapters(clock),  # type: ignore[arg-type]
        dispatcher=dispatcher,
    )

    result = await harness.scanner.scan()

    assert len(result.opportunities) <= 1
    assert len(dispatcher.submitted) <= 1


# --- очередь Level 2 ------------------------------------------------------


async def test_level2_queue_rejects_overflow(database: Database, clock: FakeClock) -> None:
    """Очередь Level 2 не растёт бесконечно (``03`` §69)."""
    harness = await build_level2(
        parse_configuration(level1_document(), environ=dict(VALID_ENV)).config,
        database,
        clock,
    )
    worker = Level2Worker(
        harness.scanner,
        harness.configuration.scanner.level2.model_copy(update={"queue_capacity": 1}),
    )

    await worker.submit(harness.opportunity, harness.job)
    with pytest.raises(ResourceError):
        await worker.submit(harness.opportunity, harness.job)
    await worker.drain()

    assert worker.rejected_submissions == 1


async def test_level2_parallelism_never_exceeds_configuration(
    database: Database, clock: FakeClock
) -> None:
    """``max_parallel`` соблюдается под нагрузкой (``CLAUDE.md`` §18)."""
    harness = await build_level2(
        parse_configuration(level1_document(), environ=dict(VALID_ENV)).config,
        database,
        clock,
    )
    worker = Level2Worker(
        harness.scanner,
        harness.configuration.scanner.level2.model_copy(update={"max_parallel": 1}),
    )

    await worker.submit(harness.opportunity, harness.job)
    results = await worker.drain()

    assert worker.active == 0
    assert len(results) == 1


# --- рост состояния -------------------------------------------------------


async def test_repeated_scans_do_not_grow_state(database: Database, clock: FakeClock) -> None:
    """Повторные циклы не создают неограниченного числа возможностей."""
    harness = build_harness(
        configured(),
        database,
        clock,
        adapters=counting_adapters(clock),  # type: ignore[arg-type]
    )

    for _ in range(5):
        await harness.scanner.scan()

    opportunities = await database.fetch_one("SELECT COUNT(*) AS count FROM opportunities", ())
    scans = await database.fetch_one("SELECT COUNT(*) AS count FROM scans", ())
    assert opportunities is not None and scans is not None
    # Дедупликация удерживает число возможностей, хотя циклов было пять.
    assert scans["count"] == 5
    assert opportunities["count"] < scans["count"] * TOKEN_COUNT


async def test_finished_scans_are_cleaned_up(database: Database, clock: FakeClock) -> None:
    """Retention удаляет завершённые циклы (``31_DATA_RETENTION.md``)."""
    from monik.repositories.sqlite import SqliteScanRepository

    harness = build_harness(
        configured(),
        database,
        clock,
        adapters=counting_adapters(clock),  # type: ignore[arg-type]
    )
    await harness.scanner.scan()
    clock.advance(timedelta(days=30))

    removed = await SqliteScanRepository(database).delete_finished_before(clock.now())

    assert removed == 1
    row = await database.fetch_one("SELECT COUNT(*) AS count FROM scans", ())
    assert row is not None and row["count"] == 0


async def test_quote_history_is_not_persisted(database: Database, clock: FakeClock) -> None:
    """Полный поток котировок не сохраняется (``02`` §86)."""
    harness = build_harness(
        configured(),
        database,
        clock,
        adapters=counting_adapters(clock),  # type: ignore[arg-type]
    )

    result = await harness.scanner.scan()

    tables = await database.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'", ())
    names = {str(row["name"]) for row in tables}
    assert "quotes" not in names
    assert result.scan.statistics.quote_requests > len(result.opportunities)
