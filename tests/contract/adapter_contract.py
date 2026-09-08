"""Общий contract test suite для всех Aggregator Adapters.

Каждый adapter обязан пройти этот набор (``06_AGGREGATOR_ADAPTERS.md`` §59).
Конкретный тестовый модуль наследует :class:`AdapterContractTests` и
предоставляет фабрику адаптера.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

import pytest

from monik.domain.enums.operations import (
    OperationType,
    RouteValidationOutcome,
    RoutingMode,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import MonikError
from monik.infrastructure.providers import AggregatorAdapter, QuoteRequest
from monik.services.observability import FakeClock
from tests import factories as f


class AdapterContractTests(ABC):
    """Обязательные требования к любому адаптеру."""

    @abstractmethod
    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        """Создать адаптер, готовый вернуть валидную котировку."""

    @abstractmethod
    def expected_provider(self) -> ProviderId:
        """Ожидаемый идентификатор провайдера."""

    @pytest.fixture
    def clock(self) -> FakeClock:
        return FakeClock(f.NOW)

    @pytest.fixture
    def adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return self.make_adapter(clock)

    def buy_request(self) -> QuoteRequest:
        """Стандартный BUY-запрос USDT -> AAVE."""
        return QuoteRequest(
            network_id=f.POLYGON,
            operation=OperationType.BUY,
            input_token=f.USDT,
            output_token=f.AAVE,
            input_amount=f.USDT.amount_from_base_units(100_000_000),
            request_id=f.RequestId.generate(),
        )

    # --- контракт ---------------------------------------------------------

    def test_satisfies_protocol(self, adapter: AggregatorAdapter) -> None:
        assert isinstance(adapter, AggregatorAdapter)

    def test_reports_provider_id(self, adapter: AggregatorAdapter) -> None:
        assert adapter.provider_id is self.expected_provider()

    def test_capabilities_are_declared(self, adapter: AggregatorAdapter) -> None:
        """Поддержка сети не предполагается по умолчанию (06 §15)."""
        capabilities = adapter.capabilities
        assert capabilities.provider_id is self.expected_provider()
        assert capabilities.supported_networks
        assert capabilities.routing_modes

    async def test_quote_is_normalized(self, adapter: AggregatorAdapter) -> None:
        request = self.buy_request()
        quote = await adapter.get_quote(request)
        assert quote.provider_id is self.expected_provider()
        assert quote.network_id == request.network_id
        assert quote.input_token == request.input_token.key
        assert quote.output_token == request.output_token.key
        assert quote.input_amount == request.input_amount
        assert quote.output_amount.decimals == request.output_token.decimals

    async def test_quote_carries_route_with_fingerprint(self, adapter: AggregatorAdapter) -> None:
        quote = await adapter.get_quote(self.buy_request())
        assert quote.route.provider_id is self.expected_provider()
        assert quote.route.operation is OperationType.BUY
        assert len(str(quote.route.fingerprint)) == 64

    async def test_route_fingerprint_is_deterministic(self, adapter: AggregatorAdapter) -> None:
        first = await adapter.get_quote(self.buy_request())
        second = await adapter.get_quote(self.buy_request())
        assert first.route.fingerprint == second.route.fingerprint

    async def test_routing_mode_is_part_of_route(self, adapter: AggregatorAdapter) -> None:
        quote = await adapter.get_quote(self.buy_request())
        assert isinstance(quote.route.routing_mode, RoutingMode)

    async def test_quote_timestamp_is_utc(self, adapter: AggregatorAdapter) -> None:
        quote = await adapter.get_quote(self.buy_request())
        assert quote.created_at.tzinfo is not None

    async def test_request_id_is_propagated(self, adapter: AggregatorAdapter) -> None:
        request = self.buy_request()
        quote = await adapter.get_quote(request)
        assert str(quote.request_id) == str(request.request_id)

    async def test_fixed_route_validation_reports_outcome(self, adapter: AggregatorAdapter) -> None:
        """Молча подменять маршрут запрещено (06 §52).

        Level 2 всегда передаёт маршрут, зафиксированный Level 1, поэтому
        contract-проверка использует именно такой запрос.
        """
        fixed = await adapter.get_quote(self.buy_request())
        request = replace(self.buy_request(), fixed_route=fixed.route)
        validation = await adapter.validate_fixed_route(request)
        assert isinstance(validation.outcome, RouteValidationOutcome)
        if validation.outcome is RouteValidationOutcome.REPRODUCED:
            assert validation.quote is not None
        else:
            assert validation.quote is None

    async def test_discovers_capabilities(self, adapter: AggregatorAdapter) -> None:
        capabilities = await adapter.discover_capabilities()
        assert capabilities.provider_id is self.expected_provider()

    async def test_fee_discovery_never_invents_zero(self, adapter: AggregatorAdapter) -> None:
        """Неизвестная комиссия не превращается в ноль (06 §40)."""
        fees = await adapter.discover_fees(f.POLYGON)
        for fee in fees:
            if not fee.is_known:
                assert fee.amount is None

    async def test_health_check_returns_state(self, adapter: AggregatorAdapter) -> None:
        health = await adapter.health_check()
        assert health.provider_id is self.expected_provider()

    async def test_close_is_idempotent(self, adapter: AggregatorAdapter) -> None:
        await adapter.aclose()
        await adapter.aclose()

    async def test_errors_are_normalized(self, clock: FakeClock) -> None:
        """Provider-specific исключения не выходят наружу (38 §12)."""
        adapter = self.make_failing_adapter(clock)
        if adapter is None:
            pytest.skip("adapter does not support failure injection")
        with pytest.raises(MonikError):
            await adapter.get_quote(self.buy_request())

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter | None:
        """Адаптер, который всегда возвращает ошибку.

        Возврат ``None`` означает, что тест инъекции ошибок пропускается.
        """
        return None
