"""Confirmation Policy: сведение результатов сумм в итоговые статусы.

Каждая сумма сохраняет собственный статус, и итог этот факт не скрывает
(``11_LEVEL_2_SCANNER.md`` §46). Подтверждение возможно только при
завершённом расчёте, пройденном пороге и подтверждённом маршруте (§45).

``PARTIAL`` никогда не считается ``CONFIRMED`` (``CLAUDE.md`` §26), а
``ROUTE_UNAVAILABLE`` не смешивается с ``UNPROFITABLE`` (§51).
"""

from __future__ import annotations

from monik.domain.enums.lifecycle import (
    AmountVerificationStatus,
    JobStatus,
    OpportunityStatus,
)
from monik.domain.models.job import AmountVerificationResult

__all__ = ["job_status_for", "opportunity_status_for"]

#: Статусы, означающие определённый отрицательный вердикт.
_DEFINITIVE_NEGATIVE = frozenset(
    {
        AmountVerificationStatus.VERIFIED_UNPROFITABLE,
        AmountVerificationStatus.ROUTE_UNAVAILABLE,
    }
)


def _statuses(results: tuple[AmountVerificationResult, ...]) -> set[AmountVerificationStatus]:
    return {result.status for result in results}


def job_status_for(results: tuple[AmountVerificationResult, ...]) -> JobStatus:
    """Итоговый статус Job по результатам сумм (``35_STATE_MACHINES.md`` §18-19).

    ``CONFIRMED`` требует хотя бы одной подтверждённо прибыльной суммы;
    ``REJECTED`` — определённого отрицательного вердикта по всем суммам;
    неопределённость (``UNKNOWN``/``FAILED``) даёт ``FAILED``, а не
    отрицательный вердикт: ошибка API не является признаком убыточности
    (``11_LEVEL_2_SCANNER.md`` §53).
    """
    if not results:
        return JobStatus.FAILED
    statuses = _statuses(results)
    if AmountVerificationStatus.VERIFIED_PROFITABLE in statuses:
        return JobStatus.CONFIRMED
    if statuses == {AmountVerificationStatus.EXPIRED}:
        return JobStatus.EXPIRED
    if statuses <= _DEFINITIVE_NEGATIVE:
        return JobStatus.REJECTED
    return JobStatus.FAILED


def opportunity_status_for(
    results: tuple[AmountVerificationResult, ...],
) -> OpportunityStatus:
    """Итоговый статус Opportunity (``11_LEVEL_2_SCANNER.md`` §47).

    Смешанный результат отражается как ``PARTIAL``: часть сумм подтверждена,
    часть — нет (§46).
    """
    if not results:
        return OpportunityStatus.FAILED
    statuses = _statuses(results)
    if statuses == {AmountVerificationStatus.VERIFIED_PROFITABLE}:
        return OpportunityStatus.CONFIRMED
    if AmountVerificationStatus.VERIFIED_PROFITABLE in statuses:
        return OpportunityStatus.PARTIAL
    if statuses == {AmountVerificationStatus.VERIFIED_UNPROFITABLE}:
        return OpportunityStatus.UNPROFITABLE
    if statuses == {AmountVerificationStatus.ROUTE_UNAVAILABLE}:
        return OpportunityStatus.ROUTE_UNAVAILABLE
    if statuses == {AmountVerificationStatus.EXPIRED}:
        return OpportunityStatus.EXPIRED
    if statuses <= _DEFINITIVE_NEGATIVE:
        # Часть сумм убыточна, часть недоступна по маршруту: определённый
        # отрицательный вердикт без подтверждения прибыльности.
        return OpportunityStatus.UNPROFITABLE
    return OpportunityStatus.FAILED
