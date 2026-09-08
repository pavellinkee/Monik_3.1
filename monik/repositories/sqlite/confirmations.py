"""Атомарная публикация подтверждённой возможности.

Opportunity обязана быть сохранена **до** постановки доставки в очередь
(``15_NOTIFICATION_SYSTEM.md`` §4): статус возможности и записи уведомлений
пишутся одной транзакцией, поэтому состояние «уведомление есть, а
подтверждения нет» невозможно.

Внутри транзакции не выполняется ни одного внешнего вызова
(``30_DATABASE_SCHEMA.md`` §76-77): тексты сообщений формируются заранее.
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.lifecycle import OpportunityStatus
from monik.domain.models.notification import Notification
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import to_timestamp
from monik.repositories.sqlite.notifications import insert_notification

__all__ = ["PublishedNotification", "SqliteConfirmationRepository"]


@dataclass(frozen=True, slots=True)
class PublishedNotification:
    """Уведомление вместе с заранее сформированными текстами."""

    notification: Notification
    message_text: str | None = None
    details_text: str | None = None


class SqliteConfirmationRepository:
    """Публикует итог подтверждения одной транзакцией."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def publish(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None,
        notifications: tuple[PublishedNotification, ...],
    ) -> None:
        """Записать статус возможности и её уведомления атомарно."""
        async with self._database.transaction() as tx:
            await tx.execute(
                "UPDATE opportunities SET status = ?, updated_at = ?, "
                "confirmed_at = COALESCE(?, confirmed_at) WHERE opportunity_id = ?",
                (
                    status.value,
                    to_timestamp(updated_at),
                    to_timestamp(confirmed_at) if confirmed_at else None,
                    str(opportunity_id),
                ),
            )
            for item in notifications:
                await insert_notification(
                    tx,
                    item.notification,
                    message_text=item.message_text,
                    details_text=item.details_text,
                )
