"""Фиксированный контекст точности финансовых вычислений.

Calculator обязан быть детерминированным (``09_PROFIT_CALCULATOR.md`` §49,
§71): одинаковые входные данные дают одинаковый результат. Стандартный
``decimal`` контекст — process-wide изменяемое состояние, поэтому расчёт,
зависящий от него, детерминированным не является.

Промежуточные значения не округляются (``09_PROFIT_CALCULATOR.md`` §39):
точность задаётся заведомо избыточной, а округление выполняет presentation
layer (``09_PROFIT_CALCULATOR.md`` §40).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)

__all__ = ["CALCULATION_PRECISION", "CALCULATION_ROUNDING", "calculation_context"]

#: Значащих цифр промежуточных вычислений. Значение заведомо превышает
#: потребности токенов с 18 decimals и ROI в процентах.
CALCULATION_PRECISION = 50

#: Правило округления последнего разряда. Banker's rounding не смещает
#: результат систематически в сторону завышения прибыли.
CALCULATION_ROUNDING = ROUND_HALF_EVEN


@contextmanager
def calculation_context() -> Iterator[None]:
    """Выполнить арифметику в фиксированном контексте.

    Арифметические сбои превращаются в исключения, а не в ``NaN``/
    ``Infinity``: возвращать произвольное число запрещено
    (``09_PROFIT_CALCULATOR.md`` §72).
    """
    context = Context(
        prec=CALCULATION_PRECISION,
        rounding=CALCULATION_ROUNDING,
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    with localcontext(context):
        yield
