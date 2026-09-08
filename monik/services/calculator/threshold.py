"""Применение profitability threshold к результату расчёта.

Порог задаётся конфигурацией и не хардкодится
(``09_PROFIT_CALCULATOR.md`` §24, §51). Сравнение выполняется как ``>=``,
поэтому ровно пороговое значение проходит (``09_PROFIT_CALCULATOR.md`` §26).
"""

from __future__ import annotations

from decimal import Decimal

from monik.domain.enums.calculation import ThresholdMetric
from monik.domain.models.profit import ThresholdOutcome

__all__ = ["COST_SENSITIVE_METRICS", "evaluate_threshold"]

#: Метрики, значение которых зависит от расходов. Неизвестный расход
#: способен изменить их относительно порога (``09_PROFIT_CALCULATOR.md`` §27).
COST_SENSITIVE_METRICS = frozenset({ThresholdMetric.NET_ROI, ThresholdMetric.NET_PROFIT})


def evaluate_threshold(
    *,
    metric: ThresholdMetric,
    threshold: Decimal,
    values: dict[ThresholdMetric, Decimal],
    has_unknown_costs: bool,
) -> ThresholdOutcome:
    """Определить, пройден ли порог.

    Порог не считается пройденным, если хотя бы один расход, влияющий на
    выбранную метрику, неизвестен: неизвестная стоимость способна изменить
    результат относительно порога (``09_PROFIT_CALCULATOR.md`` §27).
    """
    actual = values.get(metric)
    blocked = has_unknown_costs and metric in COST_SENSITIVE_METRICS
    passed = actual is not None and not blocked and actual >= threshold
    return ThresholdOutcome(
        metric=metric,
        threshold=threshold,
        actual=actual,
        passed=passed,
        blocked_by_unknown_cost=blocked,
    )
