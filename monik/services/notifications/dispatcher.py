"""Доставка уведомлений: очередь, порядок, retry и изоляция назначений.

Порядок отправки определяется ``created_at`` и внутренним sequence
(``CLAUDE.md`` §37): сортировка по прибыли, приоритету, сумме или
агрегатору запрещена.

Сбой одного назначения не блокирует остальные
(``15_NOTIFICATION_SYSTEM.md`` §55) и не приводит к повторной отправке
уже доставленного уведомления (§57).

Ошибка Telegram не отменяет подтверждённую возможность (§24): статус
получает уведомление, а не Opportunity.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta

from monik.config.sections.notifications import NotificationConfig
from monik.domain.enums.lifecycle import NotificationStatus
from monik.domain.enums.notifications import DeliveryErrorKind
from monik.domain.models.notification import Notification, NotificationAttempt
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.services.notifications.formatter import DETAILS_BUTTON_LABEL
from monik.services.notifications.ports import (
    DeliveryReceipt,
    NotificationStore,
    NotificationTransport,
    OutgoingMessage,
)
from monik.services.observability import names
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields
from monik.services.observability.metrics import MetricsRegistry

__all__ = ["DeliveryReport", "NotificationDispatcher", "details_callback_data"]

_LOGGER = get_logger("services.notifications.dispatcher")

#: Префикс callback-данных кнопки ``об``.
DETAILS_CALLBACK_PREFIX = "details"


def details_callback_data(notification_id: str) -> str:
    """Данные кнопки ``об`` для конкретного уведомления.

    Ссылаются на сохранённое уведомление, поэтому обработка нажатия читает
    подготовленный текст и не выполняет внешних запросов
    (``CLAUDE.md`` §35).
    """
    return f"{DETAILS_CALLBACK_PREFIX}:{notification_id}"


@dataclass
class DeliveryReport:
    """Итог одного прохода очереди."""

    delivered: list[str] = field(default_factory=list)
    retried: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def processed(self) -> int:
        """Сколько уведомлений обработано."""
        return len(self.delivered) + len(self.retried) + len(self.failed) + len(self.skipped)


class NotificationDispatcher:
    """Отправляет уведомления из очереди через настроенные транспорты."""

    def __init__(
        self,
        config: NotificationConfig,
        *,
        store: NotificationStore,
        transports: dict[str, NotificationTransport],
        clock: Clock,
        jitter: random.Random | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._transports = transports
        self._clock = clock
        self._random = jitter or random.Random(0)
        self._metrics = metrics

    async def dispatch_pending(self, *, limit: int | None = None) -> DeliveryReport:
        """Обработать очередь в порядке формирования уведомлений."""
        batch = min(limit or self._config.queue_capacity, self._config.queue_capacity)
        pending = await self._store.claim_pending(now=self._clock.now(), limit=batch)
        report = DeliveryReport()
        for notification in pending:
            await self._deliver(notification, report)
        return report

    async def recover_interrupted(self) -> tuple[Notification, ...]:
        """Вернуть в очередь уведомления, застрявшие в ``SENDING``.

        Прерванная отправка не считается доставленной без подтверждения
        (``15_NOTIFICATION_SYSTEM.md`` §61): уведомление возвращается в
        очередь, а уже отправленные (``SENT``) не трогаются (§60).
        """
        interrupted = await self._store.list_by_status(
            NotificationStatus.SENDING, limit=self._config.queue_capacity
        )
        now = self._clock.now()
        for notification in interrupted:
            await self._store.update_delivery_state(
                notification.notification_id,
                NotificationStatus.QUEUED,
                updated_at=now,
                next_attempt_at=None,
            )
            _LOGGER.warning(
                "notification delivery was interrupted",
                extra=log_fields(notification_id=notification.notification_id),
            )
        return interrupted

    # --- внутреннее -------------------------------------------------------

    async def _deliver(self, notification: Notification, report: DeliveryReport) -> None:
        destination = notification.destination
        transport = self._transports.get(destination.kind.value)
        with log_context(request_id=notification.notification_id):
            if transport is None:
                await self._fail(
                    notification,
                    DeliveryErrorKind.DESTINATION_ERROR,
                    f"no transport for {destination.kind.value}",
                    report,
                )
                return

            message_text, _ = await self._store.load_texts(notification.notification_id)
            invalid = _validation_error(message_text)
            if invalid is not None or message_text is None:
                # Некорректное сообщение не отправляется (§68-69).
                await self._fail(
                    notification,
                    DeliveryErrorKind.INVALID_REQUEST,
                    invalid or "notification has no prepared message text",
                    report,
                )
                return

            started_at = self._clock.now()
            attempt_number = notification.attempt_count + 1
            await self._store.update_delivery_state(
                notification.notification_id,
                NotificationStatus.SENDING,
                updated_at=started_at,
                attempt_count=attempt_number,
            )
            receipt = await transport.send(
                OutgoingMessage(
                    destination=destination,
                    text=message_text,
                    # Кнопка «об» присутствует в каждом уведомлении
                    # (``CLAUDE.md`` §35).
                    details_callback=details_callback_data(notification.notification_id),
                    details_label=DETAILS_BUTTON_LABEL,
                )
            )
            await self._apply(notification, attempt_number, started_at, receipt, report)

    async def _apply(
        self,
        notification: Notification,
        attempt_number: int,
        started_at: UtcDatetime,
        receipt: DeliveryReceipt,
        report: DeliveryReport,
    ) -> None:
        finished_at = self._clock.now()
        if receipt.delivered:
            await self._record(
                notification,
                attempt_number,
                started_at,
                finished_at,
                NotificationStatus.SENT,
                external_message_id=receipt.external_message_id,
            )
            await self._store.update_delivery_state(
                notification.notification_id,
                NotificationStatus.SENT,
                updated_at=finished_at,
                attempt_count=attempt_number,
            )
            report.delivered.append(notification.notification_id)
            self._count(outcome="delivered")
            return

        kind = receipt.error_kind or DeliveryErrorKind.UNKNOWN_ERROR
        exhausted = attempt_number >= self._config.max_attempts
        retryable = kind.is_retryable and not exhausted
        status = NotificationStatus.RETRY_WAIT if retryable else NotificationStatus.FAILED
        await self._record(
            notification,
            attempt_number,
            started_at,
            finished_at,
            status,
            error_code=kind.value,
        )
        next_attempt_at = (
            finished_at + self._backoff(attempt_number, receipt.retry_after_seconds)
            if retryable
            else None
        )
        await self._store.update_delivery_state(
            notification.notification_id,
            status,
            updated_at=finished_at,
            attempt_count=attempt_number,
            next_attempt_at=next_attempt_at,
        )
        _LOGGER.warning(
            "notification delivery failed",
            extra=log_fields(
                notification_id=notification.notification_id,
                error_kind=kind.value,
                attempt=attempt_number,
                retryable=retryable,
            ),
        )
        if retryable:
            report.retried.append(notification.notification_id)
            self._count(outcome="retried")
        else:
            report.failed.append(notification.notification_id)
            self._count(outcome="failed")

    async def _fail(
        self,
        notification: Notification,
        kind: DeliveryErrorKind,
        detail: str,
        report: DeliveryReport,
    ) -> None:
        """Окончательный отказ без обращения к транспорту."""
        now = self._clock.now()
        attempt_number = notification.attempt_count + 1
        await self._record(
            notification,
            attempt_number,
            now,
            now,
            NotificationStatus.FAILED,
            error_code=kind.value,
        )
        await self._store.update_delivery_state(
            notification.notification_id,
            NotificationStatus.FAILED,
            updated_at=now,
            attempt_count=attempt_number,
        )
        _LOGGER.error(
            "notification cannot be delivered",
            extra=log_fields(error_kind=kind.value, detail=detail),
        )
        report.failed.append(notification.notification_id)
        self._count(outcome="failed")

    def _count(self, *, outcome: str) -> None:
        """Метрика доставки (``28_OBSERVABILITY.md`` §37).

        Идентификатор уведомления в labels не попадает (``28`` §42).
        """
        if self._metrics is not None:
            self._metrics.increment(names.NOTIFICATIONS, outcome=outcome)

    async def _record(
        self,
        notification: Notification,
        attempt_number: int,
        started_at: UtcDatetime,
        finished_at: UtcDatetime,
        status: NotificationStatus,
        *,
        error_code: str | None = None,
        external_message_id: str | None = None,
    ) -> None:
        await self._store.record_attempt(
            notification.notification_id,
            NotificationAttempt(
                attempt_number=attempt_number,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                error_code=error_code,
                external_message_id=external_message_id,
            ),
        )

    def _backoff(self, attempt_number: int, retry_after_seconds: float | None) -> timedelta:
        """Задержка перед повтором (``15_NOTIFICATION_SYSTEM.md`` §26-28).

        ``Retry-After`` провайдера имеет приоритет над расчётной задержкой:
        игнорировать его нельзя (``CLAUDE.md`` §32).
        """
        if retry_after_seconds is not None:
            return timedelta(seconds=retry_after_seconds)
        base = self._config.retry_initial_delay_seconds * (2 ** (attempt_number - 1))
        capped = min(base, self._config.retry_max_delay_seconds)
        return timedelta(seconds=capped * (0.5 + self._random.random() / 2))


def _validation_error(message_text: str | None) -> str | None:
    """Причина, по которой сообщение нельзя отправлять (§68)."""
    if message_text is None:
        return "notification has no prepared message text"
    if not message_text.strip():
        return "notification message text is empty"
    return None
