"""Восстановление незавершённого состояния после запуска.

Порядок старта (``CLAUDE.md`` §30) требует восстановить состояние до
инициализации воркеров.

Ключевые правила:

* Level 2 Job, оставшийся ``RUNNING`` во время аварии, считается
  прерванным; новая попытка начинает проверку **заново**;
* старые котировки свежими не считаются: они не переиспользуются, а
  запрашиваются заново;
* runtime-локи не восстанавливаются — они живут только в памяти процесса;
* уведомления, застрявшие в ``SENDING``, не считаются доставленными
  (``15_NOTIFICATION_SYSTEM.md`` §61).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from monik.domain.enums.base import DomainEnum
from monik.domain.enums.lifecycle import JobStatus, NotificationStatus, OpportunityStatus
from monik.domain.models.job import Level2Job
from monik.domain.models.notification import Notification
from monik.domain.models.opportunity import Opportunity
from monik.repositories.sqlite.jobs import SqliteJobRepository
from monik.repositories.sqlite.notifications import SqliteNotificationRepository
from monik.repositories.sqlite.opportunities import SqliteOpportunityRepository
from monik.services.observability.clock import Clock
from monik.services.observability.events import TransitionRecorder
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["RecoveryReport", "RecoveryService"]

_LOGGER = get_logger("app.recovery")

#: Причина перевода прерванного Job в очередь.
INTERRUPTED_REASON = "interrupted_by_restart"

#: Сколько записей обрабатывается за один проход восстановления.
_BATCH_LIMIT = 500


@dataclass
class RecoveryReport:
    """Что было восстановлено при старте."""

    requeued_jobs: list[str] = field(default_factory=list)
    expired_jobs: list[str] = field(default_factory=list)
    expired_opportunities: list[str] = field(default_factory=list)
    requeued_notifications: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Общее число восстановленных записей."""
        return (
            len(self.requeued_jobs)
            + len(self.expired_jobs)
            + len(self.expired_opportunities)
            + len(self.requeued_notifications)
        )


class RecoveryService:
    """Приводит незавершённое состояние в согласованный вид."""

    def __init__(
        self,
        *,
        jobs: SqliteJobRepository,
        opportunities: SqliteOpportunityRepository,
        notifications: SqliteNotificationRepository,
        clock: Clock,
        transitions: TransitionRecorder | None = None,
    ) -> None:
        self._jobs = jobs
        self._opportunities = opportunities
        self._notifications = notifications
        self._clock = clock
        self._transitions = transitions

    async def recover(self) -> RecoveryReport:
        """Восстановить состояние; повторный вызов не создаёт дублей."""
        report = RecoveryReport()
        now = self._clock.now()
        await self._recover_jobs(report, now=now)
        await self._expire_opportunities(report, now=now)
        await self._recover_notifications(report, now=now)
        _LOGGER.info("recovery finished", extra=log_fields(restored=report.total))
        return report

    # --- Level 2 ----------------------------------------------------------

    async def _recover_jobs(self, report: RecoveryReport, *, now: datetime) -> None:
        """Прерванные и просроченные Job.

        ``RUNNING`` после аварийного рестарта не является доказательством
        успеха (``35_STATE_MACHINES.md`` §135).
        """
        for job in await self._jobs.list_interrupted():
            await self._recover_job(job, report, now=now)
        for job in await self._jobs.list_expired(now=now, limit=_BATCH_LIMIT):
            if job.k_id in report.expired_jobs:
                continue
            await self._expire_job(job, report, now=now)

    async def _recover_job(self, job: Level2Job, report: RecoveryReport, *, now: datetime) -> None:
        if job.is_expired(now):
            await self._expire_job(job, report, now=now)
            return
        # Новая попытка начнёт проверку заново: сохранённые котировки
        # Level 1 и предыдущей попытки свежими не считаются.
        await self._jobs.update_status(job.k_id, JobStatus.QUEUED, updated_at=now)
        await self._record(
            entity_type="level2_job",
            entity_id=str(job.k_id),
            from_state=JobStatus.RUNNING,
            to_state=JobStatus.QUEUED,
            reason=INTERRUPTED_REASON,
        )
        report.requeued_jobs.append(str(job.k_id))
        _LOGGER.warning("interrupted level 2 job requeued", extra=log_fields(k_id=str(job.k_id)))

    async def _expire_job(self, job: Level2Job, report: RecoveryReport, *, now: datetime) -> None:
        await self._jobs.update_status(job.k_id, JobStatus.EXPIRED, updated_at=now)
        await self._record(
            entity_type="level2_job",
            entity_id=str(job.k_id),
            from_state=job.status,
            to_state=JobStatus.EXPIRED,
            reason="expired_before_restart",
        )
        report.expired_jobs.append(str(job.k_id))

    # --- Opportunity ------------------------------------------------------

    async def _expire_opportunities(self, report: RecoveryReport, *, now: datetime) -> None:
        """Просроченная возможность не отправляется как актуальная."""
        for opportunity in await self._opportunities.list_expired(now=now, limit=_BATCH_LIMIT):
            await self._expire_opportunity(opportunity, report, now=now)

    async def _expire_opportunity(
        self, opportunity: Opportunity, report: RecoveryReport, *, now: datetime
    ) -> None:
        await self._opportunities.update_status(
            opportunity.opportunity_id, OpportunityStatus.EXPIRED, updated_at=now
        )
        await self._record(
            entity_type="opportunity",
            entity_id=str(opportunity.v_id),
            from_state=opportunity.status,
            to_state=OpportunityStatus.EXPIRED,
            reason="expired_before_restart",
        )
        report.expired_opportunities.append(str(opportunity.v_id))

    # --- уведомления ------------------------------------------------------

    async def _recover_notifications(self, report: RecoveryReport, *, now: datetime) -> None:
        """Прерванная отправка не считается доставленной (``15`` §61).

        Уже отправленные уведомления не трогаются, поэтому повторной
        доставки не возникает (``15`` §60).
        """
        interrupted = await self._notifications.list_by_status(
            NotificationStatus.SENDING, limit=_BATCH_LIMIT
        )
        for notification in interrupted:
            await self._requeue_notification(notification, report, now=now)

    async def _requeue_notification(
        self, notification: Notification, report: RecoveryReport, *, now: datetime
    ) -> None:
        await self._notifications.update_delivery_state(
            notification.notification_id,
            NotificationStatus.QUEUED,
            updated_at=now,
            next_attempt_at=None,
        )
        await self._record(
            entity_type="notification",
            entity_id=notification.notification_id,
            from_state=NotificationStatus.SENDING,
            to_state=NotificationStatus.QUEUED,
            reason=INTERRUPTED_REASON,
        )
        report.requeued_notifications.append(notification.notification_id)

    async def _record(
        self,
        *,
        entity_type: str,
        entity_id: str,
        from_state: DomainEnum | None,
        to_state: DomainEnum,
        reason: str,
    ) -> None:
        """Зафиксировать переход, если журнал переходов подключён."""
        if self._transitions is None:
            return
        await self._transitions.record(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
