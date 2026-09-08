"""Создание Opportunity и немедленная передача Level 2 Job.

Opportunity и её Job создаются **атомарно** (``CLAUDE.md`` §29,
``10_LEVEL_1_SCANNER.md`` §85): состояние «Opportunity есть, Job потерян»
недопустимо. Только после успешной фиксации Job передаётся в обработку —
не дожидаясь следующего цикла (``02_LEVEL1_SCANNER.md`` §46).

Level 1 не выполняет подтверждение сам (``10_LEVEL_1_SCANNER.md`` §61) и не
отправляет уведомления (§62).
"""

from __future__ import annotations

from datetime import timedelta

from monik.domain.enums.lifecycle import JobStatus, OpportunityStatus
from monik.domain.enums.resources import RequestPriority
from monik.domain.models.job import Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.identifiers import KId, OpportunityId, ScanId, VId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.repositories.sqlite.sequences import JOB_SEQUENCE, OPPORTUNITY_SEQUENCE
from monik.services.level1.grouping import CandidateGroup
from monik.services.level1.ports import IdSequenceSource, Level2Dispatcher, OpportunityStore
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["OpportunityHandoff"]

_LOGGER = get_logger("services.level1.handoff")


class OpportunityHandoff:
    """Фиксирует найденную возможность и передаёт её Level 2."""

    def __init__(
        self,
        *,
        store: OpportunityStore,
        sequences: IdSequenceSource,
        dispatcher: Level2Dispatcher,
        clock: Clock,
        opportunity_ttl: timedelta,
        job_ttl: timedelta,
    ) -> None:
        self._store = store
        self._sequences = sequences
        self._dispatcher = dispatcher
        self._clock = clock
        self._opportunity_ttl = opportunity_ttl
        self._job_ttl = job_ttl

    async def create(self, group: CandidateGroup, *, scan_id: ScanId) -> Opportunity:
        """Создать Opportunity с Job и немедленно передать его."""
        now = self._clock.now()
        opportunity = await self._build(group, scan_id=scan_id, now=now)
        job = await self._build_job(opportunity, now=now)
        with log_context(
            scan_id=str(scan_id),
            v_id=str(opportunity.v_id),
            k_id=str(job.k_id),
            network=str(opportunity.network_id),
        ):
            await self._store.create_with_job(opportunity, job)
            await self._dispatcher.submit(opportunity, job)
            _LOGGER.info(
                "opportunity handed off to level 2",
                extra=log_fields(
                    buy_provider=opportunity.buy_provider_id.value,
                    sell_provider=opportunity.sell_provider_id.value,
                    amounts=len(opportunity.amounts),
                    fingerprint=str(opportunity.fingerprint),
                ),
            )
        return opportunity

    async def _build(
        self, group: CandidateGroup, *, scan_id: ScanId, now: UtcDatetime
    ) -> Opportunity:
        sequence = await self._sequences.next_value(OPPORTUNITY_SEQUENCE)
        return Opportunity(
            opportunity_id=OpportunityId.generate(),
            v_id=VId.from_sequence(sequence),
            scan_id=scan_id,
            status=OpportunityStatus.CREATED,
            buy_provider_id=group.buy_provider_id,
            sell_provider_id=group.sell_provider_id,
            routes=group.routes,
            amounts=group.amounts,
            detected_at=now,
            expires_at=now + self._opportunity_ttl,
        )

    async def _build_job(self, opportunity: Opportunity, *, now: UtcDatetime) -> Level2Job:
        """Job получает приоритет выше нового Level 1 scan (§45)."""
        sequence = await self._sequences.next_value(JOB_SEQUENCE)
        return Level2Job(
            k_id=KId.from_sequence(sequence),
            opportunity_id=opportunity.opportunity_id,
            status=JobStatus.QUEUED,
            priority=RequestPriority.LEVEL2,
            created_at=now,
            updated_at=now,
            expires_at=now + self._job_ttl,
        )
