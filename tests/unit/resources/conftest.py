"""Общие средства для тестов Resource Manager."""

from __future__ import annotations

import random
from datetime import timedelta

import pytest

from monik.config.sections.resources import (
    CircuitBreakerConfig,
    ResourceConfig,
    RetryConfig,
)
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.services.observability import FakeClock
from tests import factories as f


class ControlledSleeper:
    """Ожидание без реального времени.

    Продвигает управляемые часы, поэтому rate limiter и circuit breaker
    видят прошедшее время, а тест выполняется мгновенно.
    """

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
        self._clock.advance(timedelta(seconds=seconds))

    @property
    def total_slept(self) -> float:
        return sum(self.delays)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
def sleeper(clock: FakeClock) -> ControlledSleeper:
    return ControlledSleeper(clock)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(20260101)


def resource_config(**overrides: object) -> ResourceConfig:
    """Конфигурация Resource Manager с быстрыми значениями по умолчанию."""
    base: dict[str, object] = {
        "global_max_concurrent_requests": 4,
        "queue_capacity": 16,
        "queue_wait_timeout_seconds": 5.0,
        "retry": RetryConfig(
            max_attempts=3,
            initial_delay_seconds=0.1,
            max_delay_seconds=2.0,
            backoff_multiplier=2.0,
            jitter_ratio=0.0,
        ),
        "circuit_breaker": CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout_seconds=10.0, success_threshold=1
        ),
    }
    base.update(overrides)
    return ResourceConfig(**base)  # type: ignore[arg-type]


def request(
    *,
    priority: RequestPriority = RequestPriority.LEVEL1_BUY,
    sequence: int = 0,
    provider: ProviderId = ProviderId.ONEINCH,
    operation: CapabilityOperation | None = None,
    timeout_seconds: float = 5.0,
    deduplication_key: str | None = None,
    batch_units: int = 1,
    created_at: object = None,
) -> ResourceRequest:
    """Запрос к ресурсу с предсказуемыми параметрами."""
    return ResourceRequest(
        request_id=f.RequestId.generate(),
        key=ResourceKey(provider_id=provider, network_id=f.POLYGON, operation=operation),
        priority=priority,
        timeout=timedelta(seconds=timeout_seconds),
        created_at=created_at or f.NOW,  # type: ignore[arg-type]
        sequence=sequence,
        deduplication_key=deduplication_key,
        batch_units=batch_units,
    )
