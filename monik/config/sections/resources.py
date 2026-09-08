"""Конфигурация Resource Manager."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection

__all__ = ["CircuitBreakerConfig", "ResourceConfig", "RetryConfig"]


class RetryConfig(ConfigSection):
    """Политика повторов (``17_CONFIGURATION.md`` §42-43, ``CLAUDE.md`` §32).

    Бесконечные повторы невозможны: ``max_attempts`` ограничен сверху.
    """

    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=0.5, gt=0, le=60)
    max_delay_seconds: float = Field(default=30.0, gt=0, le=600)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    respect_retry_after: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.initial_delay_seconds > self.max_delay_seconds:
            raise ValueError("initial_delay_seconds must not exceed max_delay_seconds")
        if not self.respect_retry_after:
            raise ValueError(
                "respect_retry_after must remain true: HTTP 429 responses must honour "
                "the Retry-After header"
            )
        return self


class CircuitBreakerConfig(ConfigSection):
    """Параметры circuit breaker (``12_RESOURCE_MANAGER.md`` §31-35).

    Circuit breaker отражает временную недоступность и не изменяет
    Capability Registry (``05_RESOURCE_MANAGER.md`` §11).
    """

    enabled: bool = True
    failure_threshold: int = Field(default=5, ge=1, le=100)
    recovery_timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    half_open_max_calls: int = Field(default=1, ge=1, le=50)
    success_threshold: int = Field(default=2, ge=1, le=50)


class ResourceConfig(ConfigSection):
    """Лимиты и политики Resource Manager (``17_CONFIGURATION.md`` §41).

    Неограниченная конкурентность запрещена
    (``05_RESOURCE_MANAGER.md`` §61): все лимиты имеют верхнюю границу.
    """

    global_max_concurrent_requests: int = Field(default=32, ge=1, le=1024)
    queue_capacity: int = Field(default=1000, ge=1, le=100_000)
    queue_wait_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    default_request_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    lease_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    deduplicate_in_flight: bool = True
    retry: RetryConfig = RetryConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
