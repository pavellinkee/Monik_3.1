"""Сборка адаптеров с контролируемыми зависимостями."""

from __future__ import annotations

import json
import random
from typing import Any

from monik.config.secrets import SecretRef, SecretResolver, SecretValue
from monik.config.sections.providers import ProviderConfig
from monik.config.sections.resources import (
    CircuitBreakerConfig,
    ResourceConfig,
    RetryConfig,
)
from monik.domain.enums.providers import ProviderId
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.services.observability import FakeClock
from monik.services.resources import ResourceManager
from tests import factories as f

API_KEY_ENV = "MONIK_TEST_API_KEY"
API_KEY_VALUE = "test-provider-api-key-value"


def secret() -> SecretValue:
    """Разрешённый тестовый секрет."""
    return SecretResolver({API_KEY_ENV: API_KEY_VALUE}).resolve(
        SecretRef(env=API_KEY_ENV), context="test"
    )


def provider_config(provider_id: ProviderId, **overrides: object) -> ProviderConfig:
    """Конфигурация провайдера для тестов."""
    base: dict[str, object] = {
        "provider_id": provider_id,
        "enabled": True,
        "supported_networks": (f.POLYGON,),
        "request_timeout_seconds": 5.0,
    }
    base.update(overrides)
    return ProviderConfig(**base)  # type: ignore[arg-type]


def resource_manager(clock: FakeClock) -> ResourceManager:
    """Resource Manager без реальных задержек."""

    async def sleeper(seconds: float) -> None:
        return None

    return ResourceManager(
        ResourceConfig(
            global_max_concurrent_requests=4,
            queue_capacity=32,
            retry=RetryConfig(max_attempts=2, initial_delay_seconds=0.01, jitter_ratio=0.0),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        ),
        clock,
        sleeper=sleeper,
        rng=random.Random(1),
    )


def json_response(payload: Any, status: int = 200) -> HttpResponse:
    """Успешный JSON-ответ."""
    return HttpResponse(status_code=status, text=json.dumps(payload))


def http_returning(payload: Any, status: int = 200) -> FakeHttpClient:
    """Клиент, всегда возвращающий один и тот же ответ."""
    return FakeHttpClient(handler=lambda request: json_response(payload, status))
