"""Profit Calculator — единственный владелец финансовых формул.

Подсистема реализует ``09_PROFIT_CALCULATOR.md``. Scanner, Telegram и
история финансовых формул не содержат: они передают нормализованные данные
и получают детерминированный результат (§2, §30).
"""

from monik.services.calculator.conversion import RateBook
from monik.services.calculator.costs import aggregate_costs
from monik.services.calculator.precision import (
    CALCULATION_PRECISION,
    CALCULATION_ROUNDING,
    calculation_context,
)
from monik.services.calculator.profit import ProfitCalculator
from monik.services.calculator.threshold import COST_SENSITIVE_METRICS, evaluate_threshold

__all__ = [
    "CALCULATION_PRECISION",
    "CALCULATION_ROUNDING",
    "COST_SENSITIVE_METRICS",
    "ProfitCalculator",
    "RateBook",
    "aggregate_costs",
    "calculation_context",
    "evaluate_threshold",
]
