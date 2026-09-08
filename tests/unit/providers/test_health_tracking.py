"""Наблюдение за доступностью провайдера при обычных обращениях."""

from __future__ import annotations

import pytest

from monik.config.sections.health import HealthConfig
from monik.domain.enums.health import AdapterState, ProviderHealthStatus
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError, UnsupportedError
from monik.infrastructure.providers import QuoteRequest
from monik.infrastructure.providers.contract import AdapterHealth
from monik.infrastructure.providers.fake import FakeAdapter
from monik.infrastructure.providers.health_tracking import HealthTrackingAdapter
from monik.services.health import HealthMonitor
from monik.services.observability import FakeClock
from tests import factories as f


def _monitor(clock: FakeClock) -> HealthMonitor:
    return HealthMonitor(
        HealthConfig(provider_degraded_threshold=2, provider_failure_threshold=3),
        clock,
    )


def _request() -> QuoteRequest:
    return QuoteRequest(
        network_id=f.POLYGON,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_amount=f.USDT.amount_from_base_units(100_000_000),
        request_id=f.RequestId.generate(),
    )


class FailingAdapter(FakeAdapter):
    """Адаптер, отвечающий заданной ошибкой."""

    def __init__(self, clock: FakeClock, error: Exception) -> None:
        super().__init__(ProviderId.UNISWAP, clock)
        self._error = error

    async def get_quote(self, request: QuoteRequest) -> object:
        raise self._error

    async def health_check(self) -> AdapterHealth:
        return AdapterHealth(provider_id=ProviderId.UNISWAP, state=AdapterState.DEGRADED)


class TestObservation:
    async def test_successful_quote_is_recorded(self) -> None:
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        adapter = HealthTrackingAdapter(FakeAdapter(ProviderId.UNISWAP, clock), monitor)
        await adapter.get_quote(_request())
        await adapter.get_quote(_request())
        assert monitor.provider(ProviderId.UNISWAP).status is ProviderHealthStatus.HEALTHY

    async def test_provider_error_degrades_after_the_threshold(self) -> None:
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        adapter = HealthTrackingAdapter(
            FailingAdapter(clock, ProviderError("upstream unavailable")), monitor
        )
        for _ in range(2):
            with pytest.raises(ProviderError):
                await adapter.get_quote(_request())
        assert monitor.provider(ProviderId.UNISWAP).status is ProviderHealthStatus.DEGRADED

    async def test_error_is_not_swallowed(self) -> None:
        clock = FakeClock(f.NOW)
        adapter = HealthTrackingAdapter(
            FailingAdapter(clock, ProviderError("upstream unavailable")), _monitor(clock)
        )
        with pytest.raises(ProviderError):
            await adapter.get_quote(_request())

    async def test_unsupported_operation_is_not_a_provider_failure(self) -> None:
        """Health ≠ capability (``19_HEALTH_MONITORING.md`` §55)."""
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        adapter = HealthTrackingAdapter(
            FailingAdapter(clock, UnsupportedError("network not supported")), monitor
        )
        with pytest.raises(UnsupportedError):
            await adapter.get_quote(_request())
        assert monitor.provider(ProviderId.UNISWAP).status is ProviderHealthStatus.UNKNOWN

    async def test_health_check_is_not_counted_as_a_runtime_observation(self) -> None:
        """Явная проверка интерпретируется вызывающей стороной (§38-39)."""
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        adapter = HealthTrackingAdapter(FailingAdapter(clock, ProviderError("x")), monitor)
        await adapter.health_check()
        assert monitor.provider(ProviderId.UNISWAP).status is ProviderHealthStatus.UNKNOWN

    def test_wrapped_adapter_is_reachable(self) -> None:
        clock = FakeClock(f.NOW)
        inner = FakeAdapter(ProviderId.UNISWAP, clock)
        adapter = HealthTrackingAdapter(inner, _monitor(clock))
        assert adapter.wrapped is inner
        assert adapter.provider_id is ProviderId.UNISWAP
        assert adapter.capabilities is inner.capabilities


class TestProbeRecording:
    def test_probe_applies_immediately(self) -> None:
        """Иначе неработающий провайдер остался бы UNKNOWN после старта."""
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        monitor.record_provider_probe(
            ProviderId.UNISWAP, ProviderHealthStatus.UNAVAILABLE, reason="http_client_error"
        )
        health = monitor.provider(ProviderId.UNISWAP)
        assert health.status is ProviderHealthStatus.UNAVAILABLE
        assert health.reason == "http_client_error"

    def test_successful_probe_marks_provider_healthy(self) -> None:
        clock = FakeClock(f.NOW)
        monitor = _monitor(clock)
        monitor.record_provider_probe(ProviderId.UNISWAP, ProviderHealthStatus.HEALTHY)
        assert monitor.provider(ProviderId.UNISWAP).status is ProviderHealthStatus.HEALTHY
