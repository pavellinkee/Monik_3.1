"""Результат одного цикла Level 1."""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.lifecycle import ScanStatus
from monik.domain.models.opportunity import Opportunity
from monik.domain.models.scan import Scan
from monik.services.level1.quotes import QuoteAttempt

__all__ = ["ScanResult"]


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Итог цикла: метаданные, созданные Opportunity и диагностика.

    Состав соответствует ``10_LEVEL_1_SCANNER.md`` §76 и
    ``02_LEVEL1_SCANNER.md`` §57.
    """

    scan: Scan
    opportunities: tuple[Opportunity, ...] = ()
    failures: tuple[QuoteAttempt, ...] = ()

    @property
    def status(self) -> ScanStatus:
        """Статус цикла."""
        return self.scan.status

    @property
    def is_complete(self) -> bool:
        """Полностью ли успешен цикл.

        PARTIAL полностью успешным не считается
        (``02_LEVEL1_SCANNER.md`` §54).
        """
        return self.scan.status is ScanStatus.COMPLETE
