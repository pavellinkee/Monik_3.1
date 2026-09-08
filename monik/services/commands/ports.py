"""Порты обработчиков команд.

Все данные читаются из репозиториев и уже собранных снимков: **ни один
обработчик не инициирует запрос к провайдеру** (``CLAUDE.md`` §35,
``15_NOTIFICATION_SYSTEM.md`` §6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from monik.domain.enums.lifecycle import JobStatus
from monik.domain.models.job import ConfirmationResult, Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.identifiers import KId, OpportunityId
from monik.services.opportunity.statistics import ConfirmationStatistics

__all__ = [
    "ComponentStatus",
    "JobReader",
    "NotificationReader",
    "OpportunityReader",
    "StatsSnapshot",
    "StatsSource",
    "StatusSource",
]


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """Состояние одной подсистемы для ``/status``."""

    name: str
    state: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    """Агрегированная статистика для ``/stats``.

    Confirmation rate считается по формуле ``CLAUDE.md`` §27 и может быть
    ``N/A``: отсутствие решений нельзя показывать как ноль процентов.
    """

    confirmations: ConfirmationStatistics = field(default_factory=ConfirmationStatistics)
    scans_completed: int = 0
    opportunities_created: int = 0
    notifications_sent: int = 0


@runtime_checkable
class JobReader(Protocol):
    """Чтение Level 2 Job и сохранённых результатов проверки."""

    async def get(self, k_id: KId) -> Level2Job | None:
        """Найти Job по ``#K``."""
        ...

    async def list_by_status(self, status: JobStatus, *, limit: int) -> tuple[Level2Job, ...]:
        """Job'ы в указанном статусе."""
        ...

    async def load_confirmation(self, k_id: KId, revision: int) -> ConfirmationResult | None:
        """Сохранённый результат проверки."""
        ...


@runtime_checkable
class OpportunityReader(Protocol):
    """Чтение Opportunity."""

    async def get(self, opportunity_id: OpportunityId) -> Opportunity | None:
        """Найти возможность по идентификатору."""
        ...


@runtime_checkable
class NotificationReader(Protocol):
    """Чтение подготовленных текстов уведомления."""

    async def load_texts(self, notification_id: str) -> tuple[str | None, str | None]:
        """Тексты сообщения и кнопки ``об``."""
        ...


@runtime_checkable
class StatusSource(Protocol):
    """Снимок состояния подсистем."""

    def components(self) -> tuple[ComponentStatus, ...]:
        """Текущее состояние подсистем."""
        ...


@runtime_checkable
class StatsSource(Protocol):
    """Источник агрегированной статистики."""

    def snapshot(self) -> StatsSnapshot:
        """Текущая статистика."""
        ...
