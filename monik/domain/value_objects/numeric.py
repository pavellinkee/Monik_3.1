"""Точные числовые типы для финансовых значений.

Binary floating point запрещён для любых финансовых расчётов
(``CLAUDE.md`` §11, ``09_PROFIT_CALCULATOR.md`` §3, ``36_DATA_MODELS.md`` §4).
Поэтому типы ниже **отклоняют** ``float`` на входе, а не молча приводят его.

Правило разделения представлений (``09_PROFIT_CALCULATOR.md`` §4):

* raw blockchain amounts -> ``int`` (base units);
* деньги, проценты, курсы -> ``Decimal``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

__all__ = [
    "BaseUnits",
    "NonNegativeDecimal",
    "PositiveDecimal",
    "SignedDecimal",
    "to_decimal",
]


class FloatNotAllowedError(ValueError):
    """Попытка использовать ``float`` там, где требуется точная арифметика."""

    def __init__(self, value: object) -> None:
        super().__init__(
            f"binary float is not allowed for financial values, got {value!r}; "
            "use Decimal or a decimal string"
        )


def _reject_float(value: Any) -> Any:
    """Отклонить ``float`` до любой конвертации.

    ``bool`` является подклассом ``int``, а не ``float``, поэтому проверка
    затрагивает только настоящие числа с плавающей точкой.
    """
    if isinstance(value, float):
        raise FloatNotAllowedError(value)
    return value


def _reject_bool(value: Any) -> Any:
    """Отклонить ``bool`` там, где ожидается целое количество base units."""
    if isinstance(value, bool):
        raise ValueError(f"bool is not a valid amount, got {value!r}")
    return value


def _to_decimal(value: Any) -> Any:
    """Привести ``int``/``str`` к ``Decimal`` без потери точности."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"invalid decimal literal: {value!r}") from exc
    return value


def to_decimal(value: int | str | Decimal) -> Decimal:
    """Публичный помощник конвертации в ``Decimal``.

    ``float`` не принимается намеренно — сигнатура делает это явным для mypy,
    а runtime-проверка защищает от нетипизированных вызовов.
    """
    _reject_float(value)
    result = _to_decimal(value)
    if not isinstance(result, Decimal):  # pragma: no cover - защита от нетипизированного ввода
        raise TypeError(f"cannot convert {type(value).__name__} to Decimal")
    return result


#: Произвольное точное значение: допускает отрицательные суммы (например, net profit).
SignedDecimal = Annotated[Decimal, BeforeValidator(_reject_float), BeforeValidator(_to_decimal)]

#: Значение, которое не может быть отрицательным (комиссии, gas, costs).
NonNegativeDecimal = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    BeforeValidator(_to_decimal),
    Field(ge=0),
]

#: Строго положительное значение (input amount, курс конверсии).
PositiveDecimal = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    BeforeValidator(_to_decimal),
    Field(gt=0),
]

#: Raw blockchain amount в base units. Всегда целое и неотрицательное.
BaseUnits = Annotated[
    int,
    BeforeValidator(_reject_float),
    BeforeValidator(_reject_bool),
    Field(ge=0),
]
