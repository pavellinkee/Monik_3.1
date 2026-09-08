"""Курсы конверсии между токенами."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.numeric import PositiveDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["ConversionRate"]


class ConversionRate(DomainModel):
    """Курс перевода одного токена в другой (``09_PROFIT_CALCULATOR.md`` §35).

    Направление конверсии задаётся явно: ``ETH -> USDT`` не равно
    ``USDT -> ETH`` без обратного пересчёта (``09_PROFIT_CALCULATOR.md`` §38).

    Устаревший курс не используется бесконечно (``09_PROFIT_CALCULATOR.md`` §36):
    при истечении срока расчёт становится ``PARTIAL``/``UNKNOWN``, а курс
    не экстраполируется.
    """

    from_token: TokenKey
    to_token: TokenKey
    rate: PositiveDecimal
    source: str = Field(min_length=1, max_length=128)
    observed_at: UtcDatetime
    expires_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.from_token == self.to_token:
            raise ValueError("conversion rate must reference two different tokens")
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("conversion rate expires_at must be after observed_at")
        return self

    def is_fresh(self, now: UtcDatetime) -> bool:
        """Актуален ли курс на момент ``now``."""
        return self.expires_at is None or now < self.expires_at

    def convert(self, amount: Decimal) -> Decimal:
        """Перевести сумму из ``from_token`` в ``to_token``."""
        return amount * self.rate

    def inverted(self) -> Self:
        """Вернуть обратный курс с тем же источником и временем."""
        return type(self).model_validate(
            {
                **self.model_dump(),
                "from_token": self.to_token.model_dump(),
                "to_token": self.from_token.model_dump(),
                "rate": Decimal(1) / self.rate,
            }
        )
