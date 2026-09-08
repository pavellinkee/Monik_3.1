"""Политика маршрутов и допустимых комбинаций провайдеров.

На текущем этапе маршруты фиксированные (``01_PROJECT_REQUIREMENTS.md`` §15):
Monik не строит произвольные multi-hop пути. Level 1 берёт маршрут из ответа
провайдера и фиксирует его, а конфигурация определяет, какие комбинации
вообще допустимы (``17_CONFIGURATION.md`` §30-31).
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.providers import ProviderId

__all__ = ["ProviderPair", "RoutePolicyConfig"]


class ProviderPair(ConfigSection):
    """Разрешённая пара «провайдер BUY — провайдер SELL»."""

    buy: ProviderId
    sell: ProviderId


class RoutePolicyConfig(ConfigSection):
    """Ограничения на комбинации, которые проверяет Level 1.

    Пустой ``allowed_pairs`` означает «все кросс-провайдерные комбинации
    среди enabled провайдеров», что соответствует основной модели поиска
    (``02_LEVEL1_SCANNER.md`` §18).
    """

    allow_same_provider: bool = False
    allowed_pairs: tuple[ProviderPair, ...] = ()
    max_route_steps: int = Field(default=4, ge=1, le=16)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.allow_same_provider:
            for pair in self.allowed_pairs:
                if pair.buy is pair.sell:
                    raise ValueError(
                        f"provider pair {pair.buy.value}->{pair.sell.value} uses the same "
                        "provider while allow_same_provider is false"
                    )
        seen: set[tuple[ProviderId, ProviderId]] = set()
        for pair in self.allowed_pairs:
            key = (pair.buy, pair.sell)
            if key in seen:
                raise ValueError(f"duplicate provider pair {pair.buy.value}->{pair.sell.value}")
            seen.add(key)
        return self

    def is_allowed(self, buy: ProviderId, sell: ProviderId) -> bool:
        """Разрешена ли конкретная комбинация."""
        if buy is sell and not self.allow_same_provider:
            return False
        if not self.allowed_pairs:
            return True
        return any(pair.buy is buy and pair.sell is sell for pair in self.allowed_pairs)
