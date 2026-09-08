"""Политика повторов.

Retry-оркестрация централизована в Resource Manager
(``38_INTERFACES.md`` §91): подсистемы не создают собственные циклы
повторов (``01_PROJECT_REQUIREMENTS.md`` §37).

Обязательные свойства (``CLAUDE.md`` §32, ``12_RESOURCE_MANAGER.md`` §24-27):
ограниченное число попыток, экспоненциальная задержка, jitter и учёт
заголовка ``Retry-After``.
"""

from __future__ import annotations

import random
from datetime import timedelta

from monik.config.sections.resources import RetryConfig
from monik.domain.errors.base import ErrorInfo
from monik.domain.errors.classification import is_retryable

__all__ = ["RetryPolicy"]


class RetryPolicy:
    """Решает, повторять ли операцию и с какой задержкой."""

    def __init__(self, config: RetryConfig, *, rng: random.Random | None = None) -> None:
        self._config = config
        # Отдельный генератор со стабильным seed делает jitter воспроизводимым
        # в тестах, не влияя на глобальное состояние ``random``.
        self._rng = rng or random.Random()

    @property
    def max_attempts(self) -> int:
        """Максимальное число попыток."""
        return self._config.max_attempts

    def should_retry(self, error: ErrorInfo, *, attempts_used: int) -> bool:
        """Можно ли выполнить ещё одну попытку.

        Бесконечные повторы невозможны: бюджет попыток ограничен
        конфигурацией.
        """
        return is_retryable(
            error, attempts_used=attempts_used, max_attempts=self._config.max_attempts
        )

    def delay_for(self, error: ErrorInfo, *, attempts_used: int) -> float:
        """Задержка перед следующей попыткой в секундах.

        Если провайдер прислал ``Retry-After``, он имеет приоритет над
        расчётной задержкой: игнорировать указание провайдера нельзя
        (``12_RESOURCE_MANAGER.md`` §27).
        """
        if self._config.respect_retry_after and error.retry_after is not None:
            return max(0.0, self._retry_after_seconds(error.retry_after))
        return self._backoff(attempts_used)

    def _backoff(self, attempts_used: int) -> float:
        """Экспоненциальная задержка с jitter в пределах конфигурации."""
        exponent = max(0, attempts_used)
        base = self._config.initial_delay_seconds * (self._config.backoff_multiplier**exponent)
        capped = min(base, self._config.max_delay_seconds)
        jitter_ratio = self._config.jitter_ratio
        if jitter_ratio <= 0:
            return capped
        # Jitter уменьшает задержку, но никогда не увеличивает её сверх
        # максимума: одновременные повторы не должны совпадать по времени
        # (``12_RESOURCE_MANAGER.md`` §26, §79).
        low = capped * (1 - jitter_ratio)
        return self._rng.uniform(low, capped)

    @staticmethod
    def _retry_after_seconds(retry_after: timedelta) -> float:
        return retry_after.total_seconds()
