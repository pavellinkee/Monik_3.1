"""Хранилище уведомлений."""

from __future__ import annotations

import uuid

import aiosqlite

from monik.domain.enums.lifecycle import NotificationStatus
from monik.domain.enums.notifications import DestinationKind, NotificationMode
from monik.domain.models.notification import (
    Notification,
    NotificationAttempt,
    NotificationDestination,
)
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database, Transaction
from monik.infrastructure.db.types import from_timestamp, to_timestamp
from monik.repositories.sqlite.mapping import column, optional_column

__all__ = ["SqliteNotificationRepository", "insert_notification"]

_COLUMNS = (
    "notification_id, opportunity_id, destination_id, destination_kind, mode, status, "
    "sequence, attempt_count, fingerprint, message_text, details_text, created_at, "
    "updated_at, next_attempt_at"
)

#: Статусы, из которых доставка ещё может продолжиться.
_PENDING_STATUSES = (
    NotificationStatus.QUEUED.value,
    NotificationStatus.RETRY_WAIT.value,
)


async def insert_notification(
    tx: Transaction,
    notification: Notification,
    *,
    message_text: str | None = None,
    details_text: str | None = None,
) -> None:
    """Вставить уведомление в рамках существующей транзакции.

    Позволяет записать Opportunity и её уведомления одной транзакцией:
    возможность обязана быть сохранена до постановки доставки в очередь
    (``15_NOTIFICATION_SYSTEM.md`` §4).
    """
    await tx.execute(
        f"INSERT INTO notifications ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _notification_values(notification, message_text, details_text),
    )


def _notification_values(
    notification: Notification, message_text: str | None, details_text: str | None
) -> tuple[object, ...]:
    """Позиционные значения строки уведомления."""
    return (
        notification.notification_id,
        str(notification.opportunity_id),
        notification.destination.destination_id,
        notification.destination.kind.value,
        notification.destination.mode.value,
        notification.status.value,
        notification.sequence,
        notification.attempt_count,
        str(notification.fingerprint),
        message_text,
        details_text,
        to_timestamp(notification.created_at),
        to_timestamp(notification.updated_at),
        to_timestamp(notification.next_attempt_at) if notification.next_attempt_at else None,
    )


class SqliteNotificationRepository:
    """Persistence уведомлений (``38_INTERFACES.md`` §71).

    Порядок отправки определяется ``created_at`` и ``sequence``
    (``CLAUDE.md`` §37): сортировка по прибыли, приоритету, сумме или
    агрегатору не применяется.

    Текст сообщения и текст кнопки ``об`` сохраняются вместе с уведомлением,
    поэтому обработка нажатия не выполняет новых API-запросов
    (``CLAUDE.md`` §35).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        notification: Notification,
        *,
        message_text: str | None = None,
        details_text: str | None = None,
    ) -> None:
        """Поставить уведомление в очередь."""
        await self._database.execute(
            f"INSERT INTO notifications ({_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _notification_values(notification, message_text, details_text),
        )

    async def get(self, notification_id: str) -> Notification | None:
        """Найти уведомление по идентификатору."""
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM notifications WHERE notification_id = ?",
            (notification_id,),
        )
        return self._to_domain(row) if row else None

    async def find_logical(
        self, opportunity_id: OpportunityId, destination_id: str
    ) -> Notification | None:
        """Найти logical notification ``opportunity + destination``.

        Позволяет определить, отправлялось ли уже уведомление этому
        destination (``30_DATABASE_SCHEMA.md`` §40).
        """
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM notifications WHERE opportunity_id = ? AND destination_id = ?",
            (str(opportunity_id), destination_id),
        )
        return self._to_domain(row) if row else None

    async def list_for_opportunity(self, opportunity_id: OpportunityId) -> tuple[Notification, ...]:
        """Все уведомления возможности."""
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM notifications WHERE opportunity_id = ? "
            "ORDER BY created_at, sequence",
            (str(opportunity_id),),
        )
        return tuple(self._to_domain(row) for row in rows)

    async def list_by_status(
        self, status: NotificationStatus, *, limit: int
    ) -> tuple[Notification, ...]:
        """Уведомления в указанном статусе, в порядке формирования.

        Нужен recovery: после аварии уведомления, оставшиеся в ``SENDING``,
        обрабатываются отдельной политикой
        (``15_NOTIFICATION_SYSTEM.md`` §60-61).
        """
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM notifications WHERE status = ? "
            "ORDER BY created_at, sequence LIMIT ?",
            (status.value, limit),
        )
        return tuple(self._to_domain(row) for row in rows)

    async def claim_pending(self, *, now: UtcDatetime, limit: int) -> tuple[Notification, ...]:
        """Уведомления, готовые к отправке, в порядке формирования."""
        placeholders = ", ".join("?" for _ in _PENDING_STATUSES)
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM notifications WHERE status IN ({placeholders}) "
            "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "ORDER BY created_at, sequence LIMIT ?",
            (*_PENDING_STATUSES, to_timestamp(now), limit),
        )
        return tuple(self._to_domain(row) for row in rows)

    async def update_delivery_state(
        self,
        notification_id: str,
        status: NotificationStatus,
        *,
        updated_at: UtcDatetime,
        attempt_count: int | None = None,
        next_attempt_at: UtcDatetime | None = None,
    ) -> None:
        """Обновить состояние доставки."""
        await self._database.execute(
            "UPDATE notifications SET status = ?, updated_at = ?, "
            "attempt_count = COALESCE(?, attempt_count), next_attempt_at = ? "
            "WHERE notification_id = ?",
            (
                status.value,
                to_timestamp(updated_at),
                attempt_count,
                to_timestamp(next_attempt_at) if next_attempt_at else None,
                notification_id,
            ),
        )

    async def record_attempt(self, notification_id: str, attempt: NotificationAttempt) -> str:
        """Сохранить попытку доставки."""
        attempt_id = str(uuid.uuid4())
        await self._database.execute(
            "INSERT INTO notification_attempts (attempt_id, notification_id, attempt_number, "
            "status, started_at, finished_at, error_code, external_message_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt_id,
                notification_id,
                attempt.attempt_number,
                attempt.status.value,
                to_timestamp(attempt.started_at),
                to_timestamp(attempt.finished_at) if attempt.finished_at else None,
                attempt.error_code,
                attempt.external_message_id,
            ),
        )
        return attempt_id

    async def list_attempts(self, notification_id: str) -> tuple[NotificationAttempt, ...]:
        """Попытки доставки уведомления."""
        rows = await self._database.fetch_all(
            "SELECT attempt_number, status, started_at, finished_at, error_code, "
            "external_message_id FROM notification_attempts WHERE notification_id = ? "
            "ORDER BY attempt_number",
            (notification_id,),
        )
        return tuple(self._attempt_to_domain(row) for row in rows)

    async def load_texts(self, notification_id: str) -> tuple[str | None, str | None]:
        """Сохранённые тексты сообщения и деталей для кнопки ``об``."""
        row = await self._database.fetch_one(
            "SELECT message_text, details_text FROM notifications WHERE notification_id = ?",
            (notification_id,),
        )
        if row is None:
            return (None, None)
        return (optional_column(row, "message_text"), optional_column(row, "details_text"))

    @staticmethod
    def _to_domain(row: aiosqlite.Row) -> Notification:
        next_attempt_at = optional_column(row, "next_attempt_at")
        return Notification(
            notification_id=str(column(row, "notification_id")),
            opportunity_id=OpportunityId(str(column(row, "opportunity_id"))),
            destination=NotificationDestination(
                destination_id=str(column(row, "destination_id")),
                kind=DestinationKind(str(column(row, "destination_kind"))),
                mode=NotificationMode(str(column(row, "mode"))),
            ),
            status=NotificationStatus(str(column(row, "status"))),
            sequence=int(column(row, "sequence")),
            attempt_count=int(column(row, "attempt_count")),
            created_at=from_timestamp(str(column(row, "created_at"))),
            updated_at=from_timestamp(str(column(row, "updated_at"))),
            next_attempt_at=from_timestamp(str(next_attempt_at)) if next_attempt_at else None,
        )

    @staticmethod
    def _attempt_to_domain(row: aiosqlite.Row) -> NotificationAttempt:
        finished_at = optional_column(row, "finished_at")
        return NotificationAttempt(
            attempt_number=int(column(row, "attempt_number")),
            status=NotificationStatus(str(column(row, "status"))),
            started_at=from_timestamp(str(column(row, "started_at"))),
            finished_at=from_timestamp(str(finished_at)) if finished_at else None,
            error_code=optional_column(row, "error_code"),
            external_message_id=optional_column(row, "external_message_id"),
        )
