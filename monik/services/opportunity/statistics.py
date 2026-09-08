"""Статистика подтверждений.

Confirmation rate считается как

``CONFIRMED / (CONFIRMED + UNCONFIRMED) × 100``

``PARTIAL`` из расчёта исключается (``CLAUDE.md`` §27): неопределённый
результат не является ни подтверждением, ни опровержением. Если нет ни
одного ``CONFIRMED`` и ни одного ``UNCONFIRMED``, значение — ``N/A``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from monik.domain.models.job import ConfirmationResult

__all__ = ["ConfirmationStatistics"]


@dataclass(frozen=True, slots=True)
class ConfirmationStatistics:
    """Накопленные счётчики подтверждений."""

    confirmed: int = 0
    unconfirmed: int = 0
    partial: int = 0

    def merged_with(self, result: ConfirmationResult) -> ConfirmationStatistics:
        """Учесть результат одной проверки."""
        return ConfirmationStatistics(
            confirmed=self.confirmed + result.confirmed_count,
            unconfirmed=self.unconfirmed + result.unconfirmed_count,
            partial=self.partial + result.partial_count,
        )

    @property
    def decided(self) -> int:
        """Число сумм с определённым результатом."""
        return self.confirmed + self.unconfirmed

    @property
    def confirmation_rate(self) -> Decimal | None:
        """Доля подтверждённых сумм в процентах либо ``None`` (``N/A``)."""
        if self.decided == 0:
            return None
        return Decimal(self.confirmed) * 100 / Decimal(self.decided)
