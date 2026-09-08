"""Интерфейс хранилища Opportunity."""

from __future__ import annotations

from typing import Protocol

from monik.domain.enums.lifecycle import OpportunityStatus
from monik.domain.models.job import Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.fingerprints import OpportunityFingerprint
from monik.domain.value_objects.identifiers import OpportunityId, VId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["OpportunityRepository"]


class OpportunityRepository(Protocol):
    """Persistence сущности Level 1 (``38_INTERFACES.md`` §70).

    Repository не принимает решения о прибыльности и не выбирает маршрут —
    он только сохраняет и читает состояние.
    """

    async def create_with_job(self, opportunity: Opportunity, job: Level2Job) -> None:
        """Атомарно сохранить Opportunity вместе с её Level 2 Job.

        Состояние «Opportunity есть, а необходимый Job потерян» недопустимо
        (``CLAUDE.md`` §29).
        """
        ...

    async def get(self, opportunity_id: OpportunityId) -> Opportunity | None:
        """Найти по внутреннему идентификатору."""
        ...

    async def get_by_v_id(self, v_id: VId) -> Opportunity | None:
        """Найти по публичному идентификатору ``#V``."""
        ...

    async def find_recent_by_fingerprint(
        self, fingerprint: OpportunityFingerprint, *, since: UtcDatetime
    ) -> Opportunity | None:
        """Найти логически такую же возможность в окне дедупликации."""
        ...

    async def update_status(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None = None,
    ) -> None:
        """Изменить статус возможности."""
        ...

    async def list_by_status(
        self, status: OpportunityStatus, *, limit: int
    ) -> tuple[Opportunity, ...]:
        """Возможности в указанном статусе."""
        ...

    async def list_expired(self, *, now: UtcDatetime, limit: int) -> tuple[Opportunity, ...]:
        """Незавершённые возможности, у которых истёк срок проверки."""
        ...
