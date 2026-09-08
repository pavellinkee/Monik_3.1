"""Opportunity Service — фиксация подтверждения и постановка доставки.

Возможность переводится в ``CONFIRMED``/``PARTIAL`` только после успешного
Level 2 confirmation (``35_STATE_MACHINES.md`` §60): неподтверждённая
возможность пользователю не отправляется
(``15_NOTIFICATION_SYSTEM.md`` §7).

Порядок обязателен: снимок и статус сохраняются **до** постановки доставки
в очередь, одной транзакцией и без внешних вызовов внутри неё
(``15_NOTIFICATION_SYSTEM.md`` §4, ``30_DATABASE_SCHEMA.md`` §76-77).

Финансовый снимок неизменяем (``35_STATE_MACHINES.md`` §66): переход между
notification-статусами ничего не пересчитывает (§65).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from monik.domain.enums.lifecycle import NotificationStatus, OpportunityStatus
from monik.domain.models.confirmation import ConfirmationSnapshot
from monik.domain.models.job import ConfirmationResult
from monik.domain.models.notification import Notification, NotificationDestination
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.identifiers import OpportunityId
from monik.repositories.sqlite.sequences import NOTIFICATION_SEQUENCE
from monik.services.level2.confirmation import opportunity_status_for
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields
from monik.services.opportunity.ports import (
    ConfirmationPublisher,
    MessageRenderer,
    NotificationLog,
    OpportunityStatusStore,
    PublishedNotification,
    SequenceSource,
)
from monik.services.opportunity.snapshot import build_snapshot
from monik.services.opportunity.statistics import ConfirmationStatistics

__all__ = ["ConfirmationOutcome", "DeliveryOutcome", "OpportunityService"]

_LOGGER = get_logger("services.opportunity")

#: Статусы, при которых возможность подтверждена и подлежит доставке
#: (``15_NOTIFICATION_SYSTEM.md`` §7, ``CLAUDE.md`` §26).
_NOTIFIABLE = frozenset({OpportunityStatus.CONFIRMED, OpportunityStatus.PARTIAL})


@dataclass(frozen=True, slots=True)
class ConfirmationOutcome:
    """Итог фиксации подтверждения."""

    status: OpportunityStatus
    snapshot: ConfirmationSnapshot
    notifications: tuple[Notification, ...] = ()
    already_recorded: bool = False

    @property
    def is_notifiable(self) -> bool:
        """Подлежит ли возможность доставке."""
        return self.status in _NOTIFIABLE


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    """Результат доставки по одному назначению."""

    destination_id: str
    delivered: bool


@dataclass
class OpportunityService:
    """Владелец жизненного цикла подтверждённой возможности."""

    publisher: ConfirmationPublisher
    notifications: NotificationLog
    opportunities: OpportunityStatusStore
    sequences: SequenceSource
    clock: Clock
    destinations: tuple[NotificationDestination, ...] = ()
    renderer: MessageRenderer | None = None
    statistics: ConfirmationStatistics = field(default_factory=ConfirmationStatistics)

    async def record_confirmation(
        self, opportunity: Opportunity, result: ConfirmationResult
    ) -> ConfirmationOutcome:
        """Зафиксировать результат Level 2 и поставить доставку в очередь.

        Повторная доставка того же события не создаёт вторую возможность и
        второй набор уведомлений (``11_LEVEL_2_SCANNER.md`` §70,
        ``03_LEVEL2_SCANNER.md`` §57-58).
        """
        snapshot = build_snapshot(opportunity, result)
        status = opportunity_status_for(result.amount_results)
        self.statistics = self.statistics.merged_with(result)

        with log_context(v_id=str(opportunity.v_id), k_id=str(result.k_id)):
            if status not in _NOTIFIABLE:
                # Неподтверждённая возможность в очередь доставки не попадает.
                await self.opportunities.update_status(
                    opportunity.opportunity_id, status, updated_at=self.clock.now()
                )
                _LOGGER.info("opportunity not confirmed", extra=log_fields(status=status.value))
                return ConfirmationOutcome(status=status, snapshot=snapshot)

            existing = await self.notifications.list_for_opportunity(opportunity.opportunity_id)
            if existing:
                _LOGGER.info(
                    "confirmation already recorded",
                    extra=log_fields(notifications=len(existing)),
                )
                return ConfirmationOutcome(
                    status=status,
                    snapshot=snapshot,
                    notifications=existing,
                    already_recorded=True,
                )

            queued = await self._build_notifications(snapshot)
            await self.publisher.publish(
                opportunity.opportunity_id,
                status,
                updated_at=snapshot.confirmed_at,
                confirmed_at=snapshot.confirmed_at,
                notifications=queued,
            )
            _LOGGER.info(
                "confirmation recorded",
                extra=log_fields(status=status.value, notifications=len(queued)),
            )
            return ConfirmationOutcome(
                status=status,
                snapshot=snapshot,
                notifications=tuple(item.notification for item in queued),
            )

    async def record_delivery(
        self, opportunity_id: OpportunityId, outcomes: tuple[DeliveryOutcome, ...]
    ) -> OpportunityStatus:
        """Перевести возможность в notification-статус.

        Переход ничего не пересчитывает (``35_STATE_MACHINES.md`` §65):
        меняется только статус.
        """
        status = delivery_status_for(outcomes)
        await self.opportunities.update_status(opportunity_id, status, updated_at=self.clock.now())
        return status

    async def _build_notifications(
        self, snapshot: ConfirmationSnapshot
    ) -> tuple[PublishedNotification, ...]:
        """Подготовить записи уведомлений до открытия транзакции.

        Номера последовательности выдаются заранее: внутри транзакции
        публикации не должно быть других записей, кроме её собственных.
        """
        now = self.clock.now()
        texts = self.renderer.render(snapshot) if self.renderer is not None else (None, None)
        prepared = []
        for destination in self.destinations:
            sequence = await self.sequences.next_value(NOTIFICATION_SEQUENCE)
            prepared.append(
                PublishedNotification(
                    notification=Notification(
                        notification_id=str(uuid.uuid4()),
                        opportunity_id=snapshot.opportunity_id,
                        destination=destination,
                        status=NotificationStatus.QUEUED,
                        sequence=sequence,
                        created_at=now,
                        updated_at=now,
                    ),
                    message_text=texts[0],
                    details_text=texts[1],
                )
            )
        return tuple(prepared)


def delivery_status_for(outcomes: tuple[DeliveryOutcome, ...]) -> OpportunityStatus:
    """Notification-статус по результатам доставки (``35_STATE_MACHINES.md`` §62-64).

    Частичный успех отражается отдельным статусом: сбой одного назначения
    не скрывает успешную доставку остальным
    (``15_NOTIFICATION_SYSTEM.md`` §4).
    """
    if not outcomes:
        return OpportunityStatus.NOTIFIED_FAILED
    delivered = sum(1 for outcome in outcomes if outcome.delivered)
    if delivered == len(outcomes):
        return OpportunityStatus.NOTIFIED
    if delivered == 0:
        return OpportunityStatus.NOTIFIED_FAILED
    return OpportunityStatus.NOTIFIED_PARTIAL
