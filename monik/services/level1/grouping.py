"""Группировка кандидатов в Opportunity.

Разные суммы принадлежат одной Opportunity только при совпадении пары
провайдеров и обоих маршрутов (``10_LEVEL_1_SCANNER.md`` §54): все суммы
одной Opportunity обязаны использовать **один и тот же** маршрут (§24, §89).

Route snapshot строится из тех же котировок, на основании которых создана
Opportunity (``10_LEVEL_1_SCANNER.md`` §84).
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.providers import ProviderId
from monik.domain.models.opportunity import (
    Candidate,
    OpportunityAmount,
    RouteSnapshot,
    opportunity_fingerprint,
)
from monik.domain.value_objects.fingerprints import OpportunityFingerprint

__all__ = ["CandidateGroup", "group_candidates"]


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    """Кандидаты одной логической возможности."""

    buy_provider_id: ProviderId
    sell_provider_id: ProviderId
    routes: RouteSnapshot
    candidates: tuple[Candidate, ...]

    @property
    def amounts(self) -> tuple[OpportunityAmount, ...]:
        """Amount-контексты, отсортированные по возрастанию суммы."""
        ordered = sorted(self.candidates, key=lambda item: item.buy_quote.input_amount.raw)
        return tuple(candidate.to_amount_context() for candidate in ordered)

    @property
    def fingerprint(self) -> OpportunityFingerprint:
        """Отпечаток будущей Opportunity.

        Вычисляется до её создания той же функцией, что использует сама
        модель, поэтому дедупликация не расходится с хранимым значением.
        """
        return opportunity_fingerprint(
            routes=self.routes,
            buy_provider_id=self.buy_provider_id,
            sell_provider_id=self.sell_provider_id,
        )

    @property
    def group_key(self) -> tuple[str, str, str, str]:
        """Детерминированный ключ группы."""
        return (
            self.buy_provider_id.value,
            self.sell_provider_id.value,
            str(self.routes.buy_route.fingerprint),
            str(self.routes.sell_route.fingerprint),
        )


def group_candidates(candidates: tuple[Candidate, ...]) -> tuple[CandidateGroup, ...]:
    """Сгруппировать кандидатов по паре провайдеров и паре маршрутов.

    Кандидат с той же суммой внутри группы не дублируется: сумма в
    Opportunity уникальна.
    """
    buckets: dict[tuple[str, str, str, str], list[Candidate]] = {}
    snapshots: dict[tuple[str, str, str, str], Candidate] = {}
    for candidate in candidates:
        routes = candidate.route_snapshot
        key = (
            candidate.buy_quote.provider_id.value,
            candidate.sell_quote.provider_id.value,
            str(routes.buy_route.fingerprint),
            str(routes.sell_route.fingerprint),
        )
        bucket = buckets.setdefault(key, [])
        if any(
            item.buy_quote.input_amount.raw == candidate.buy_quote.input_amount.raw
            for item in bucket
        ):
            continue
        bucket.append(candidate)
        snapshots.setdefault(key, candidate)

    groups = []
    for key in sorted(buckets):
        members = tuple(buckets[key])
        reference = snapshots[key]
        groups.append(
            CandidateGroup(
                buy_provider_id=reference.buy_quote.provider_id,
                sell_provider_id=reference.sell_quote.provider_id,
                routes=reference.route_snapshot,
                candidates=members,
            )
        )
    return tuple(groups)
