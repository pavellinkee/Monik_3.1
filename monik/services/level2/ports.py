"""Порты Level 2.

Level 2 зависит от протоколов, а не от конкретных реализаций. Источники
стоимости общие с Level 1 (``monik.services.cost_ports``): собственной
формулы газа и provider-specific fee logic у Level 2 нет
(``11_LEVEL_2_SCANNER.md`` §32, §36).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from monik.domain.enums.lifecycle import JobStatus, OpportunityStatus
from monik.domain.models.job import ConfirmationResult, Level2Attempt, Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.identifiers import KId, OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.services.cost_ports import FeeSnapshotSource, GasSource, RateSource

__all__ = [
    "FeeSnapshotSource",
    "GasSource",
    "JobStore",
    "OpportunityRegistry",
    "RateSource",
]


@runtime_checkable
class JobStore(Protocol):
    """Хранилище Level 2 Job, его попыток и результатов проверки."""

    async def get(self, k_id: KId) -> Level2Job | None:
        """Найти Job по ``#K``."""
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

    async def record_attempt(self, attempt: Level2Attempt, *, k_id: KId) -> str:
        """Сохранить попытку проверки (retry — новая попытка того же ``#K``)."""
        ...

    async def save_confirmation(self, result: ConfirmationResult) -> None:
        """Сохранить результат проверки со всеми суммами атомарно."""
        ...

    async def load_confirmation(self, k_id: KId, revision: int) -> ConfirmationResult | None:
        """Прочитать сохранённый результат проверки (идемпотентность, §70)."""
        ...


@runtime_checkable
class OpportunityRegistry(Protocol):
    """Доступ к Opportunity — источнику истины Level 2 (§4)."""

    async def get(self, opportunity_id: OpportunityId) -> Opportunity | None:
        """Найти возможность по идентификатору."""
        ...

    async def update_status(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None = None,
    ) -> None:
        """Изменить статус возможности, не трогая её финансовый снимок."""
        ...
