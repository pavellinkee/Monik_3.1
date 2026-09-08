"""Входные данные и результат финансового расчёта.

Формулы реализует Profit Calculator (этап S11); здесь определены только
контракты данных (``36_DATA_MODELS.md`` §28-31,
``09_PROFIT_CALCULATOR.md`` §31-32).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.calculation import CalculationStatus, ThresholdMetric
from monik.domain.models.base import DomainModel
from monik.domain.models.conversion import ConversionRate
from monik.domain.models.fee import Fee
from monik.domain.models.gas import Gas
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.amounts import Percentage, TokenAmount
from monik.domain.value_objects.numeric import NonNegativeDecimal, SignedDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["CostBreakdown", "ProfitCalculationInput", "ProfitResult", "ThresholdOutcome"]

#: Версия финансовой формулы. Изменение формулы обязано увеличивать версию,
#: чтобы исторические результаты не интерпретировались новыми правилами
#: (``09_PROFIT_CALCULATOR.md`` §67-68).
PROFIT_FORMULA_VERSION = 1


class ProfitCalculationInput(DomainModel):
    """Полный набор данных для одного расчёта (``09_PROFIT_CALCULATOR.md`` §31).

    Calculator не выполняет внешних запросов и не обращается к БД
    (``09_PROFIT_CALCULATOR.md`` §74): всё необходимое приходит здесь.
    """

    input_amount: TokenAmount
    input_token: TokenKey
    buy_output: TokenAmount
    intermediate_token: TokenKey
    sell_output: TokenAmount
    output_token: TokenKey
    fees: tuple[Fee, ...] = ()
    gas: Gas | None = None
    conversion_rates: tuple[ConversionRate, ...] = ()
    threshold: SignedDecimal
    threshold_metric: ThresholdMetric = ThresholdMetric.NET_ROI
    formula_version: int = Field(default=PROFIT_FORMULA_VERSION, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.input_amount.raw <= 0:
            raise ValueError("input amount must be positive")
        if self.input_token.network_id != self.output_token.network_id:
            raise ValueError("cross-network calculation is not supported")
        if self.intermediate_token.network_id != self.input_token.network_id:
            raise ValueError("intermediate token belongs to a different network")
        if self.gas is not None and self.gas.network_id != self.input_token.network_id:
            raise ValueError("gas belongs to a different network")
        return self


class CostBreakdown(DomainModel):
    """Разбивка расходов (``09_PROFIT_CALCULATOR.md`` §33).

    Каждый компонент сохраняется отдельно, чтобы результат можно было
    восстановить и проверить (``09_PROFIT_CALCULATOR.md`` §69).
    """

    total_fees: NonNegativeDecimal
    gas_cost: NonNegativeDecimal
    other_costs: NonNegativeDecimal
    rebates: NonNegativeDecimal
    unknown_components: tuple[str, ...] = ()

    @property
    def total_costs(self) -> Decimal:
        """Итоговые расходы: ``fees + gas + other − rebates``."""
        return self.total_fees + self.gas_cost + self.other_costs - self.rebates


class ThresholdOutcome(DomainModel):
    """Результат применения порога (``09_PROFIT_CALCULATOR.md`` §50)."""

    metric: ThresholdMetric
    threshold: SignedDecimal
    actual: SignedDecimal | None
    passed: bool
    blocked_by_unknown_cost: bool = False

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Неизвестный расход не позволяет считать порог пройденным.

        Соответствует ``09_PROFIT_CALCULATOR.md`` §27: если неизвестная
        стоимость способна изменить результат относительно порога, порог
        не считается пройденным.
        """
        if self.blocked_by_unknown_cost and self.passed:
            raise ValueError("threshold cannot pass while a required cost is unknown")
        if self.actual is None and self.passed:
            raise ValueError("threshold cannot pass without an actual metric value")
        return self


class ProfitResult(DomainModel):
    """Результат финансового расчёта (``36_DATA_MODELS.md`` §29).

    Отрицательная прибыль сохраняется как есть и не заменяется нулём
    (``09_PROFIT_CALCULATOR.md`` §22).
    """

    status: CalculationStatus
    profit_currency: TokenKey
    input_amount: TokenAmount
    final_output: TokenAmount
    gross_profit: SignedDecimal | None = None
    gross_roi: Percentage | None = None
    costs: CostBreakdown | None = None
    net_profit: SignedDecimal | None = None
    net_roi: Percentage | None = None
    threshold_outcome: ThresholdOutcome | None = None
    invalid_reason: str | None = Field(default=None, max_length=256)
    formula_version: int = Field(default=PROFIT_FORMULA_VERSION, ge=1)
    calculated_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """``COMPLETE`` требует полного набора рассчитанных значений.

        Причина невозможности расчёта фиксируется явно
        (``09_PROFIT_CALCULATOR.md`` §73): молчаливое исправление данных
        запрещено, поэтому ``INVALID`` обязан нести объяснение.
        """
        if self.status is CalculationStatus.INVALID and not self.invalid_reason:
            raise ValueError("INVALID calculation must carry an explicit reason")
        if self.status is not CalculationStatus.INVALID and self.invalid_reason:
            raise ValueError("invalid_reason is only meaningful for an INVALID calculation")
        if self.status is CalculationStatus.COMPLETE:
            missing = [
                name
                for name, value in (
                    ("gross_profit", self.gross_profit),
                    ("gross_roi", self.gross_roi),
                    ("costs", self.costs),
                    ("net_profit", self.net_profit),
                    ("net_roi", self.net_roi),
                    ("threshold_outcome", self.threshold_outcome),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"COMPLETE calculation is missing: {', '.join(missing)}")
            if self.costs is not None and self.costs.unknown_components:
                raise ValueError(
                    "calculation with unknown cost components cannot be COMPLETE; "
                    f"unknown: {', '.join(self.costs.unknown_components)}"
                )
        return self

    @property
    def is_profitable(self) -> bool:
        """Подтверждена ли прибыльность.

        Только полный расчёт с пройденным порогом считается подтверждением
        (``11_LEVEL_2_SCANNER.md`` §45).
        """
        return (
            self.status is CalculationStatus.COMPLETE
            and self.threshold_outcome is not None
            and self.threshold_outcome.passed
        )
