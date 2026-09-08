"""Порты Notification System."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from monik.domain.enums.lifecycle import NotificationStatus
from monik.domain.enums.notifications import DeliveryErrorKind
from monik.domain.models.notification import (
    Notification,
    NotificationAttempt,
    NotificationDestination,
)
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["DeliveryReceipt", "NotificationStore", "NotificationTransport", "OutgoingMessage"]


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    """Сообщение, готовое к отправке.

    Тексты сформированы заранее: транспорт ничего не пересчитывает и не
    форматирует (``15_NOTIFICATION_SYSTEM.md`` §14).
    """

    destination: NotificationDestination
    text: str
    details_callback: str | None = None
    details_label: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Итог одной попытки доставки (``15_NOTIFICATION_SYSTEM.md`` §22-23)."""

    delivered: bool
    external_message_id: str | None = None
    error_kind: DeliveryErrorKind | None = None
    error_message: str | None = None
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.delivered and self.error_kind is not None:
            raise ValueError("successful delivery must not carry an error kind")
        if not self.delivered and self.error_kind is None:
            raise ValueError("failed delivery must carry an explicit error kind")


@runtime_checkable
class NotificationTransport(Protocol):
    """Канал доставки. Провайдер-специфика скрыта за адаптером (§10)."""

    async def send(self, message: OutgoingMessage) -> DeliveryReceipt:
        """Отправить сообщение и вернуть нормализованный результат."""
        ...


@runtime_checkable
class NotificationStore(Protocol):
    """Persistence уведомлений (``15_NOTIFICATION_SYSTEM.md`` §59)."""

    async def claim_pending(self, *, now: UtcDatetime, limit: int) -> tuple[Notification, ...]:
        """Уведомления, готовые к отправке, в порядке формирования."""
        ...

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
        ...

    async def record_attempt(self, notification_id: str, attempt: NotificationAttempt) -> str:
        """Сохранить попытку доставки."""
        ...

    async def load_texts(self, notification_id: str) -> tuple[str | None, str | None]:
        """Сохранённые тексты сообщения и кнопки ``об``."""
        ...

    async def list_for_opportunity(self, opportunity_id: OpportunityId) -> tuple[Notification, ...]:
        """Все уведомления возможности."""
        ...

    async def list_by_status(
        self, status: NotificationStatus, *, limit: int
    ) -> tuple[Notification, ...]:
        """Уведомления в указанном статусе."""
        ...
