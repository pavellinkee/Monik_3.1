"""Notification: цель доставки, попытки и состояние."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.lifecycle import NotificationStatus
from monik.domain.enums.notifications import DestinationKind, NotificationMode
from monik.domain.models.base import DomainModel
from monik.domain.value_objects.fingerprints import NotificationFingerprint, compute_fingerprint
from monik.domain.value_objects.identifiers import OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Notification", "NotificationAttempt", "NotificationDestination"]


class NotificationDestination(DomainModel):
    """Цель доставки уведомления.

    Destination является configuration/operational identity и не может быть
    произвольным внешним вводом (``36_DATA_MODELS.md`` §83).
    """

    destination_id: str = Field(min_length=1, max_length=64)
    kind: DestinationKind
    mode: NotificationMode = NotificationMode.A


class NotificationAttempt(DomainModel):
    """Одна попытка доставки (``30_DATABASE_SCHEMA.md`` §39)."""

    attempt_number: int = Field(ge=1)
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None
    status: NotificationStatus
    error_code: str | None = Field(default=None, max_length=128)
    external_message_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("attempt finished_at must not precede started_at")
        return self


class Notification(DomainModel):
    """Логическое уведомление ``opportunity + destination``.

    Порядок отправки определяется ``created_at`` и ``sequence`` и не зависит
    от прибыльности, приоритета, суммы или агрегатора (``CLAUDE.md`` §37).

    Повторная отправка уже доставленного уведомления не выполняется
    автоматически (``35_STATE_MACHINES.md`` §81).
    """

    notification_id: str = Field(min_length=1, max_length=64)
    opportunity_id: OpportunityId
    destination: NotificationDestination
    status: NotificationStatus
    sequence: int = Field(ge=1)
    attempt_count: int = Field(default=0, ge=0)
    created_at: UtcDatetime
    updated_at: UtcDatetime
    next_attempt_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("notification updated_at must not precede created_at")
        if self.status is NotificationStatus.RETRY_WAIT and self.next_attempt_at is None:
            raise ValueError("notification in RETRY_WAIT must define next_attempt_at")
        return self

    @property
    def fingerprint(self) -> NotificationFingerprint:
        """Отпечаток logical notification для защиты от дублей."""
        return NotificationFingerprint(
            compute_fingerprint(
                {
                    "opportunity_id": str(self.opportunity_id),
                    "destination_id": self.destination.destination_id,
                    "kind": self.destination.kind.value,
                }
            )
        )

    @property
    def is_terminal(self) -> bool:
        """Завершена ли доставка окончательно."""
        return self.status in {
            NotificationStatus.SENT,
            NotificationStatus.FAILED,
            NotificationStatus.CANCELLED,
        }

    @property
    def ordering_key(self) -> tuple[UtcDatetime, int]:
        """Ключ сортировки очереди отправки (``CLAUDE.md`` §37)."""
        return (self.created_at, self.sequence)
