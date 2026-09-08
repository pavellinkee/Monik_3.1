"""Статусы и метрики финансового расчёта."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class CalculationStatus(DomainEnum):
    """Статус результата Profit Calculator (``09_PROFIT_CALCULATOR.md`` §17-21).

    Только ``COMPLETE`` допускает использование результата как полноценной
    оценки прибыльности. ``PARTIAL`` не является подтверждением прибыльности.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class ThresholdMetric(DomainEnum):
    """Метрика, к которой применяется profitability threshold.

    По умолчанию — ``NET_ROI`` (``09_PROFIT_CALCULATOR.md`` §25).
    """

    NET_ROI = "net_roi"
    GROSS_ROI = "gross_roi"
    NET_PROFIT = "net_profit"
