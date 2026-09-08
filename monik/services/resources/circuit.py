"""Circuit breaker для внешних ресурсов.

Состояния ``CLOSED`` / ``OPEN`` / ``HALF_OPEN`` (``CLAUDE.md`` §33,
``12_RESOURCE_MANAGER.md`` §31-35).

Circuit breaker отражает **временную** недоступность и не изменяет
Capability Registry (``05_RESOURCE_MANAGER.md`` §11): временный сбой не
означает отсутствие поддержки операции.
"""

from __future__ import annotations

from monik.config.sections.resources import CircuitBreakerConfig
from monik.domain.enums.resources import CircuitState
from monik.services.observability.clock import Clock

__all__ = ["CircuitBreaker"]


class CircuitBreaker:
    """Ограничивает поток запросов к недоступному ресурсу."""

    def __init__(self, config: CircuitBreakerConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Текущее состояние с учётом истёкшего времени восстановления."""
        if self._state is CircuitState.OPEN and self._recovery_elapsed():
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            self._successes = 0
        return self._state

    def allows_request(self) -> bool:
        """Разрешён ли следующий запрос.

        В ``HALF_OPEN`` пропускается ограниченное число пробных запросов
        (``12_RESOURCE_MANAGER.md`` §34).
        """
        if not self._config.enabled:
            return True
        state = self.state
        if state is CircuitState.CLOSED:
            return True
        if state is CircuitState.OPEN:
            return False
        return self._half_open_calls < self._config.half_open_max_calls

    def on_request_started(self) -> None:
        """Учесть начало пробного запроса в ``HALF_OPEN``."""
        if self.state is CircuitState.HALF_OPEN:
            self._half_open_calls += 1

    def on_success(self) -> None:
        """Учесть успешную операцию."""
        if not self._config.enabled:
            return
        # Обращение к ``state`` применяет отложенный переход OPEN -> HALF_OPEN,
        # если время восстановления уже истекло.
        if self.state is CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self._config.success_threshold:
                self._close()
            return
        self._failures = 0

    def on_failure(self) -> None:
        """Учесть неуспешную операцию."""
        if not self._config.enabled:
            return
        if self.state is CircuitState.HALF_OPEN:
            self._open()
            return
        self._failures += 1
        if self._failures >= self._config.failure_threshold:
            self._open()

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock.monotonic()
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0

    def _close(self) -> None:
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0

    def _recovery_elapsed(self) -> bool:
        if self._opened_at is None:
            return True
        elapsed = self._clock.monotonic() - self._opened_at
        return elapsed >= self._config.recovery_timeout_seconds
