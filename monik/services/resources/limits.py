"""Ограничения на использование внешних ресурсов.

Concurrency limit и rate limit — **разные** ограничения
(``12_RESOURCE_MANAGER.md`` §19): первое ограничивает число одновременных
запросов, второе — их частоту. Неограниченная конкурентность запрещена
(``05_RESOURCE_MANAGER.md`` §61).
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.services.observability.clock import Clock

__all__ = ["RateLimiter", "ResourceLimits"]


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Лимиты одного ресурса."""

    max_concurrent: int
    requests_per_second: float
    burst: int

    def __post_init__(self) -> None:
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.burst < 1:
            raise ValueError("burst must be at least 1")


class RateLimiter:
    """Token bucket с учётом стоимости запроса.

    Batch не считается автоматически одним запросом: если провайдер
    учитывает каждый элемент отдельно, стоимость передаётся явно
    (``05_RESOURCE_MANAGER.md`` §55-56, ``12_RESOURCE_MANAGER.md`` §48).
    """

    def __init__(self, limits: ResourceLimits, clock: Clock) -> None:
        self._limits = limits
        self._clock = clock
        self._tokens = float(limits.burst)
        self._updated_at = clock.monotonic()

    @property
    def available_tokens(self) -> float:
        """Доступные токены на текущий момент."""
        self._refill()
        return self._tokens

    def try_consume(self, units: int = 1) -> bool:
        """Попытаться списать стоимость запроса."""
        if units < 1:
            raise ValueError("units must be at least 1")
        self._refill()
        if self._tokens + 1e-9 < units:
            return False
        self._tokens -= units
        return True

    def wait_time(self, units: int = 1) -> float:
        """Сколько секунд ждать до появления нужного количества токенов."""
        if units < 1:
            raise ValueError("units must be at least 1")
        self._refill()
        missing = units - self._tokens
        if missing <= 0:
            return 0.0
        return missing / self._limits.requests_per_second

    def _refill(self) -> None:
        now = self._clock.monotonic()
        elapsed = now - self._updated_at
        if elapsed <= 0:
            return
        self._updated_at = now
        self._tokens = min(
            float(self._limits.burst),
            self._tokens + elapsed * self._limits.requests_per_second,
        )
