"""Политика прибыльности."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.calculation import ThresholdMetric
from monik.domain.value_objects.numeric import SignedDecimal

__all__ = ["ProfitabilityConfig"]


class ProfitabilityConfig(ConfigSection):
    """Пороги и правила подтверждения прибыльности.

    Формулы принадлежат Profit Calculator; здесь задаются только параметры
    политики (``17_CONFIGURATION.md`` §36-37). Дублировать пороги внутри
    scanner-модулей запрещено.

    Default порога — 1 % net ROI (``09_PROFIT_CALCULATOR.md`` §24), сравнение
    выполняется как ``>=``, поэтому ровно 1.00 % проходит порог
    (``09_PROFIT_CALCULATOR.md`` §26).
    """

    threshold_metric: ThresholdMetric = ThresholdMetric.NET_ROI
    final_threshold_percent: SignedDecimal = Decimal("1.00")
    preliminary_threshold_percent: SignedDecimal = Decimal("1.00")
    treat_unknown_cost_as_blocking: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Неизвестный расход не может считаться нулевым.

        Отключение этой защиты сделало бы возможным подтверждение на
        недостоверных данных (``CLAUDE.md`` §12, §55).
        """
        if not self.treat_unknown_cost_as_blocking:
            raise ValueError(
                "treat_unknown_cost_as_blocking cannot be disabled: an unknown mandatory "
                "cost must never be treated as zero"
            )
        if self.preliminary_threshold_percent > self.final_threshold_percent:
            raise ValueError(
                "preliminary threshold must not exceed the final threshold; "
                "otherwise Level 1 would discard opportunities that Level 2 would confirm"
            )
        return self
