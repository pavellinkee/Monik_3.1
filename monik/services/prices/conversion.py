"""Перевод стоимости газа в базовую валюту расчёта.

Решение D-4: конвертация native gas token в валюту расчёта (по умолчанию
USDT/USD) выполняется здесь, а не в Profit Calculator, который получает уже
нормализованные данные (``09_PROFIT_CALCULATOR.md`` §74).

Устаревший курс не используется бесконечно
(``09_PROFIT_CALCULATOR.md`` §36): при истечении срока конвертация
считается недоступной, а не экстраполируется.
"""

from __future__ import annotations

from monik.domain.models.conversion import ConversionRate
from monik.domain.models.token import Token
from monik.services.observability.clock import Clock
from monik.services.prices.providers import TokenPriceProvider

__all__ = ["ConversionService"]


class ConversionService:
    """Предоставляет актуальные курсы конверсии."""

    def __init__(
        self,
        clock: Clock,
        *,
        providers: tuple[TokenPriceProvider, ...],
    ) -> None:
        if not providers:
            raise ValueError("at least one price provider is required")
        self._clock = clock
        self._providers = providers
        self._cache: dict[tuple[str, str], ConversionRate] = {}

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Курс ``from_token -> to_token``.

        Направление учитывается явно: обратный курс не выводится из прямого
        без пересчёта (``09_PROFIT_CALCULATOR.md`` §38).
        """
        if from_token.key == to_token.key:
            return None
        cache_key = (str(from_token.key), str(to_token.key))
        cached = self._cache.get(cache_key)
        now = self._clock.now()
        if cached is not None and cached.is_fresh(now):
            return cached

        for provider in self._providers:
            rate = await provider.rate(from_token, to_token)
            if rate is not None and rate.is_fresh(now):
                self._cache[cache_key] = rate
                return rate
        return None

    def invalidate(self) -> None:
        """Сбросить кэш курсов."""
        self._cache.clear()
