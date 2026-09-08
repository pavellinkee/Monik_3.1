"""Количества токенов и процентные величины."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from monik.domain.value_objects.numeric import BaseUnits, SignedDecimal, to_decimal

__all__ = ["MAX_TOKEN_DECIMALS", "Percentage", "TokenAmount"]

#: Практический предел decimals для ERC-20. Больше — почти наверняка ошибка данных.
MAX_TOKEN_DECIMALS = 36


class TokenAmount(BaseModel):
    """Количество токена в base units плюс его ``decimals``.

    Хранится как целое (``09_PROFIT_CALCULATOR.md`` §4): raw blockchain amount
    не подлежит округлению. ``decimals`` берётся из Token Registry и
    используется только для конвертации и отображения
    (``36_DATA_MODELS.md`` §13, ``01_PROJECT_REQUIREMENTS.md`` §10).

    Модель намеренно не хранит сам ``Token``: это чистое числовое значение,
    а связь с токеном устанавливается на уровне доменных моделей, чтобы
    value objects не зависели от слоя моделей.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: BaseUnits
    decimals: int = Field(ge=0, le=MAX_TOKEN_DECIMALS)

    @property
    def as_decimal(self) -> Decimal:
        """Человекочитаемое значение с сохранением точности."""
        return Decimal(self.raw).scaleb(-self.decimals)

    @classmethod
    def from_decimal(cls, value: Decimal | int | str, decimals: int) -> Self:
        """Построить количество из человекочитаемого значения.

        Значение обязано быть представимо без потери точности при заданных
        ``decimals`` (``17_CONFIGURATION.md`` §22): иначе конфигурация или
        входные данные некорректны, и молча округлять их нельзя.
        """
        amount = to_decimal(value)
        scaled = amount.scaleb(decimals)
        if scaled != scaled.to_integral_value():
            raise ValueError(
                f"amount {amount} is not representable with {decimals} decimals "
                "without loss of precision"
            )
        return cls(raw=int(scaled), decimals=decimals)

    def with_raw(self, raw: int) -> Self:
        """Вернуть новое количество того же токена с другим raw-значением."""
        return type(self)(raw=raw, decimals=self.decimals)

    def is_zero(self) -> bool:
        """Является ли количество нулевым."""
        return self.raw == 0

    def __str__(self) -> str:
        return f"{self.as_decimal}"


class Percentage(BaseModel):
    """Процентная величина, где ``1`` означает 1 %.

    Может быть отрицательной: ROI убыточной возможности не превращается
    в ноль (``09_PROFIT_CALCULATOR.md`` §22).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: SignedDecimal

    @classmethod
    def from_ratio(cls, ratio: Decimal) -> Self:
        """Построить процент из доли (``0.01`` -> ``1 %``)."""
        return cls(value=ratio * 100)

    @property
    def as_ratio(self) -> Decimal:
        """Вернуть значение как долю."""
        return self.value / 100

    def __str__(self) -> str:
        return f"{self.value}%"
