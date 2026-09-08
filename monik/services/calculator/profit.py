"""Единственный владелец финансовых формул Monik.

Level 1, Level 2, Telegram и история используют один и тот же Calculator
(``09_PROFIT_CALCULATOR.md`` §2, §30): собственных финансовых формул у них
быть не должно.

Calculator — чистая функция над нормализованными данными: он не выполняет
внешних запросов (§74), не управляет Scheduler (§75) и не форматирует
сообщения (§76).
"""

from __future__ import annotations

from decimal import Decimal

from monik.domain.enums.calculation import CalculationStatus, ThresholdMetric
from monik.domain.models.profit import (
    PROFIT_FORMULA_VERSION,
    ProfitCalculationInput,
    ProfitResult,
)
from monik.domain.value_objects.amounts import Percentage
from monik.services.calculator.conversion import RateBook
from monik.services.calculator.costs import aggregate_costs
from monik.services.calculator.precision import calculation_context
from monik.services.calculator.threshold import evaluate_threshold
from monik.services.observability.clock import Clock

__all__ = ["ProfitCalculator"]

#: Множитель перевода доли в проценты.
_PERCENT = Decimal(100)


class ProfitCalculator:
    """Детерминированный расчёт прибыльности одной суммы.

    Каждая сумма рассчитывается в собственном контексте
    (``09_PROFIT_CALCULATOR.md`` §53): смешивать результаты разных сумм
    запрещено (§54).
    """

    def __init__(self, clock: Clock, *, formula_version: int = PROFIT_FORMULA_VERSION) -> None:
        self._clock = clock
        self._formula_version = formula_version

    @property
    def formula_version(self) -> int:
        """Версия финансовой формулы (``09_PROFIT_CALCULATOR.md`` §67)."""
        return self._formula_version

    def calculate(self, data: ProfitCalculationInput) -> ProfitResult:
        """Рассчитать прибыльность и применить порог.

        Результат всегда содержит статус расчёта: произвольное число
        вместо ошибки не возвращается (``09_PROFIT_CALCULATOR.md`` §72).
        """
        now = self._clock.now()

        reason = self._invalid_reason(data)
        if reason is not None:
            return self._result(data, status=CalculationStatus.INVALID, reason=reason)

        rates = RateBook(data.conversion_rates, now=now)
        with calculation_context():
            final_output = rates.convert(
                data.sell_output.as_decimal,
                from_token=data.output_token,
                to_token=data.input_token,
            )
            if final_output is None:
                # Валюту результата определить невозможно (§64), поэтому
                # неизвестна даже gross-прибыль (§21, §37).
                return self._result(data, status=CalculationStatus.UNKNOWN)

            input_value = data.input_amount.as_decimal
            gross_profit = final_output - input_value
            gross_roi = gross_profit / input_value * _PERCENT

            costs = aggregate_costs(
                data.fees,
                data.gas,
                currency=data.input_token,
                rates=rates,
                now=now,
            )
            net_profit = gross_profit - costs.total_costs
            net_roi = net_profit / input_value * _PERCENT

            outcome = evaluate_threshold(
                metric=data.threshold_metric,
                threshold=data.threshold,
                values={
                    ThresholdMetric.GROSS_ROI: gross_roi,
                    ThresholdMetric.NET_ROI: net_roi,
                    ThresholdMetric.NET_PROFIT: net_profit,
                },
                has_unknown_costs=bool(costs.unknown_components),
            )

        status = (
            CalculationStatus.PARTIAL if costs.unknown_components else CalculationStatus.COMPLETE
        )
        return ProfitResult(
            status=status,
            profit_currency=data.input_token,
            input_amount=data.input_amount,
            final_output=data.sell_output,
            gross_profit=gross_profit,
            gross_roi=Percentage(value=gross_roi),
            costs=costs,
            net_profit=net_profit,
            net_roi=Percentage(value=net_roi),
            threshold_outcome=outcome,
            formula_version=self._formula_version,
            calculated_at=now,
        )

    # --- внутреннее -------------------------------------------------------

    def _invalid_reason(self, data: ProfitCalculationInput) -> str | None:
        """Причина, по которой данные противоречивы (``09_PROFIT_CALCULATOR.md`` §20).

        Молчаливое исправление входных данных запрещено (§73): противоречие
        отражается статусом ``INVALID`` и явной причиной.
        """
        if data.formula_version != self._formula_version:
            return (
                f"calculation requests formula version {data.formula_version}, "
                f"calculator implements {self._formula_version}"
            )
        if data.buy_output.raw <= 0:
            return "buy output must be positive"
        if data.sell_output.raw <= 0:
            return "final output must be positive"

        network = data.input_token.network_id
        for index, fee in enumerate(data.fees):
            if fee.currency is not None and fee.currency.network_id != network:
                return f"fee[{index}] currency belongs to network {fee.currency.network_id}"
        gas = data.gas
        if gas is not None and gas.native_token is not None:
            if gas.native_token.network_id != network:
                return f"gas native token belongs to network {gas.native_token.network_id}"
        return None

    def _result(
        self,
        data: ProfitCalculationInput,
        *,
        status: CalculationStatus,
        reason: str | None = None,
    ) -> ProfitResult:
        """Результат без рассчитанных значений.

        Ни одно поле не заполняется нулём: отсутствие значения означает
        именно отсутствие (``CLAUDE.md`` §12).
        """
        return ProfitResult(
            status=status,
            profit_currency=data.input_token,
            input_amount=data.input_amount,
            final_output=data.sell_output,
            invalid_reason=reason,
            formula_version=self._formula_version,
            calculated_at=self._clock.now(),
        )
