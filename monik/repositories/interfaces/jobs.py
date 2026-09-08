"""Интерфейс хранилища Level 2 Job."""

from __future__ import annotations

from typing import Protocol

from monik.domain.enums.lifecycle import JobStatus
from monik.domain.models.job import ConfirmationResult, Level2Attempt, Level2Job
from monik.domain.value_objects.identifiers import KId, OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["JobRepository"]


class JobRepository(Protocol):
    """Persistence Level 2 Job (``38_INTERFACES.md`` §69)."""

    async def get(self, k_id: KId) -> Level2Job | None:
        """Найти Job по публичному идентификатору ``#K``."""
        ...

    async def get_by_opportunity(self, opportunity_id: OpportunityId) -> Level2Job | None:
        """Найти Job возможности.

        На одну возможность приходится максимум один логический Job
        (``CLAUDE.md`` §19).
        """
        ...

    async def update_status(
        self,
        k_id: KId,
        status: JobStatus,
        *,
        updated_at: UtcDatetime,
        attempt_count: int | None = None,
    ) -> None:
        """Изменить статус Job."""
        ...

    async def claim_queued(self, *, limit: int, now: UtcDatetime) -> tuple[Level2Job, ...]:
        """Взять из очереди Job'ы, готовые к выполнению."""
        ...

    async def list_by_status(self, status: JobStatus, *, limit: int) -> tuple[Level2Job, ...]:
        """Job'ы в указанном статусе."""
        ...

    async def list_expired(self, *, now: UtcDatetime, limit: int) -> tuple[Level2Job, ...]:
        """Незавершённые Job'ы с истёкшим сроком."""
        ...

    async def list_interrupted(self) -> tuple[Level2Job, ...]:
        """Job'ы, оставшиеся ``RUNNING`` после аварийной остановки.

        Такой Job не считается успешным (``35_STATE_MACHINES.md`` §135)
        и обрабатывается recovery-политикой.
        """
        ...

    async def record_attempt(self, attempt: Level2Attempt, *, k_id: KId) -> str:
        """Сохранить попытку проверки и вернуть её идентификатор."""
        ...

    async def save_confirmation(self, result: ConfirmationResult) -> None:
        """Сохранить результат проверки со всеми суммами."""
        ...

    async def load_confirmation(self, k_id: KId, revision: int) -> ConfirmationResult | None:
        """Прочитать сохранённый результат проверки."""
        ...
