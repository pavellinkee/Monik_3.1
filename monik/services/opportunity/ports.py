"""Порты Opportunity Service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from monik.domain.enums.lifecycle import OpportunityStatus
from monik.domain.models.confirmation import ConfirmationSnapshot
from monik.domain.models.notification import Notification
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.repositories.sqlite.confirmations import PublishedNotification

__all__ = [
    "ConfirmationPublisher",
    "MessageRenderer",
    "NotificationLog",
    "OpportunityStatusStore",
    "PublishedNotification",
    "SequenceSource",
]


@runtime_checkable
class ConfirmationPublisher(Protocol):
    """Атомарная запись статуса возможности и её уведомлений."""

    async def publish(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None,
        notifications: tuple[PublishedNotification, ...],
    ) -> None:
        """Записать итог подтверждения одной транзакцией."""
        ...


@runtime_checkable
class NotificationLog(Protocol):
    """Чтение уже поставленных уведомлений (идемпотентность)."""

    async def find_logical(
        self, opportunity_id: OpportunityId, destination_id: str
    ) -> Notification | None:
        """Найти уведомление ``opportunity + destination``."""
        ...

    async def list_for_opportunity(self, opportunity_id: OpportunityId) -> tuple[Notification, ...]:
        """Все уведомления возможности."""
        ...


@runtime_checkable
class OpportunityStatusStore(Protocol):
    """Изменение статуса возможности без правки её финансового снимка."""

    async def update_status(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None = None,
    ) -> None:
        """Перевести возможность в новый статус."""
        ...


@runtime_checkable
class SequenceSource(Protocol):
    """Монотонные номера уведомлений (порядок отправки, ``CLAUDE.md`` §37)."""

    async def next_value(self, name: str) -> int:
        """Следующий номер последовательности."""
        ...


@runtime_checkable
class MessageRenderer(Protocol):
    """Формирование текстов уведомления из готового снимка.

    Рендеринг — чистая функция над снимком: ничего не пересчитывается и
    внешние запросы не выполняются (``15_NOTIFICATION_SYSTEM.md`` §14).
    """

    def render(self, snapshot: ConfirmationSnapshot) -> tuple[str, str]:
        """Вернуть текст сообщения и текст кнопки ``об``."""
        ...
