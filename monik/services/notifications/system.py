"""Операционные уведомления о состоянии приложения.

Подсистема отвечает на вопрос «что сообщить оператору о самом Monik».
Уведомления о возможностях сюда не попадают: их доставляет
:class:`~monik.services.notifications.dispatcher.NotificationDispatcher`,
и в его очередь могут попасть только подтверждённые Opportunity
(``15_NOTIFICATION_SYSTEM.md`` §7).

Политика соответствует alerting policy (``28_OBSERVABILITY.md`` §59-65):

* одиночная transient ошибка не создаёт сообщение — состояние провайдера
  меняют пороги Health Monitoring (§60);
* повторное сообщение об уже известном состоянии отправляется не чаще
  настроенного интервала, а ошибки внутри него агрегируются;
* возврат в рабочее состояние фиксируется отдельно (``19`` §48).

Собственного состояния здоровья подсистема не ведёт: она читает снимок
Health Monitoring и запоминает лишь то, о чём уже сообщила.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from monik.config.sections.notifications import SystemNotificationConfig
from monik.domain.enums.health import ApplicationHealthStatus, ProviderHealthStatus
from monik.domain.enums.notifications import SystemAlertSeverity
from monik.domain.errors import MonikError
from monik.domain.models.health import ApplicationHealth
from monik.domain.models.notification import NotificationDestination
from monik.domain.value_objects.timestamps import UtcDatetime, ensure_utc
from monik.services.notifications.ports import NotificationTransport, OutgoingMessage
from monik.services.notifications.system_messages import (
    StartupSummary,
    aggregated_text,
    recovery_text,
    severity_for_component,
    severity_for_provider,
    startup_text,
    transition_text,
)
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["StartupSummary", "SystemNotificationState", "SystemNotifier"]

_LOGGER = get_logger("services.notifications.system")

#: Ключ, под которым хранится момент последнего сообщения о запуске.
STARTUP_NOTIFIED_KEY = "system.startup.notified_at"

#: Состояния провайдера, считающиеся рабочими.
_PROVIDER_OK = frozenset({ProviderHealthStatus.HEALTHY, ProviderHealthStatus.RECOVERING})

#: Состояния подсистемы, считающиеся рабочими.
_COMPONENT_OK = frozenset(
    {
        ApplicationHealthStatus.HEALTHY,
        ApplicationHealthStatus.STARTING,
        ApplicationHealthStatus.STOPPING,
    }
)


@runtime_checkable
class SystemNotificationState(Protocol):
    """Хранилище состояния, переживающего рестарт.

    Нужно ровно для одного: не спамить сообщениями о запуске, если процесс
    перезапускается по кругу. In-memory счётчик такой цикл не пережил бы.
    """

    async def get(self, key: str) -> str | None:
        """Значение по ключу."""
        ...

    async def set(self, key: str, value: str, *, updated_at: datetime) -> None:
        """Записать значение."""
        ...


@dataclass(frozen=True, slots=True)
class _Reported:
    """Что и когда уже было сообщено об одном субъекте."""

    status: str
    notified_at: UtcDatetime
    failures: int


class SystemNotifier:
    """Отправляет операционные уведомления с дедупликацией и агрегацией."""

    def __init__(
        self,
        config: SystemNotificationConfig,
        *,
        transport: NotificationTransport,
        destination: NotificationDestination,
        clock: Clock,
        state: SystemNotificationState | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._destination = destination
        self._clock = clock
        self._state = state
        self._reported: dict[str, _Reported] = {}

    async def notify_startup(self, summary: StartupSummary) -> bool:
        """Сообщить о завершении запуска.

        Вызывается **после** проверки готовности: до неё состояние
        подсистем неизвестно (``19_HEALTH_MONITORING.md`` §69-70).

        Возвращает ``True``, если сообщение было отправлено. При частых
        перезапусках сообщение подавляется настроенным интервалом.
        """
        if not (self._config.enabled and self._config.startup):
            return False
        now = self._now()
        if not await self._startup_allowed(now):
            _LOGGER.info("startup notification suppressed by cooldown")
            return False
        # Состояния провайдеров и подсистем уже сообщены сообщением о
        # запуске: повторять их отдельными уведомлениями не нужно.
        self._prime(summary.health, now)
        sent = await self._send(startup_text(summary))
        if sent:
            await self._remember_startup(now)
        return sent

    async def notify_health(self, health: ApplicationHealth) -> tuple[str, ...]:
        """Сообщить об изменениях состояния подсистем и провайдеров.

        Успешная работа сообщений не создаёт: без смены состояния и без
        накопленных ошибок отправлять нечего.
        """
        if not (self._config.enabled and self._config.health):
            return ()
        now = self._now()
        sent: list[str] = []
        for provider in health.providers:
            subject = f"Провайдер {provider.provider_id.value}"
            await self._observe(
                key=f"provider:{provider.provider_id.value}",
                subject=subject,
                status=provider.status.value,
                healthy=provider.status in _PROVIDER_OK,
                failures=provider.consecutive_failures,
                reason=provider.reason,
                severity=severity_for_provider(provider.status.value),
                now=now,
                sent=sent,
            )
        for component in health.components:
            await self._observe(
                key=f"component:{component.component}",
                subject=f"Подсистема {component.component}",
                status=component.status.value,
                healthy=component.status in _COMPONENT_OK,
                failures=0,
                reason=component.reason,
                severity=severity_for_component(component.status.value),
                now=now,
                sent=sent,
            )
        return tuple(sent)

    # --- внутреннее -------------------------------------------------------

    async def _observe(
        self,
        *,
        key: str,
        subject: str,
        status: str,
        healthy: bool,
        failures: int,
        reason: str | None,
        severity: SystemAlertSeverity,
        now: UtcDatetime,
        sent: list[str],
    ) -> None:
        """Решить, нужно ли сообщение об одном субъекте, и отправить его."""
        previous = self._reported.get(key)
        if previous is None:
            if healthy:
                # Рабочее состояние — не событие: запоминаем молча.
                self._reported[key] = _Reported(status, now, failures)
                return
            text = transition_text(subject, status, severity=severity, reason=reason)
        elif previous.status != status:
            text = (
                recovery_text(subject)
                if healthy
                else transition_text(subject, status, severity=severity, reason=reason)
            )
        elif healthy or not self._repeat_due(previous, now):
            return
        else:
            text = aggregated_text(subject, status, errors=max(failures - previous.failures, 0))

        if await self._send(text):
            sent.append(key)
            self._reported[key] = _Reported(status, now, failures)

    def _repeat_due(self, previous: _Reported, now: UtcDatetime) -> bool:
        """Истёк ли интервал повторного напоминания."""
        interval = timedelta(seconds=self._config.repeat_interval_seconds)
        return now - previous.notified_at >= interval

    def _prime(self, health: ApplicationHealth, now: UtcDatetime) -> None:
        """Принять текущее состояние как уже сообщённое."""
        for provider in health.providers:
            self._reported[f"provider:{provider.provider_id.value}"] = _Reported(
                provider.status.value, now, provider.consecutive_failures
            )
        for component in health.components:
            self._reported[f"component:{component.component}"] = _Reported(
                component.status.value, now, 0
            )

    async def _startup_allowed(self, now: UtcDatetime) -> bool:
        """Не слишком ли часто отправляются сообщения о запуске."""
        if self._state is None or self._config.startup_interval_seconds == 0:
            return True
        stored = await self._state.get(STARTUP_NOTIFIED_KEY)
        if stored is None:
            return True
        try:
            previous = ensure_utc(datetime.fromisoformat(stored))
        except (TypeError, ValueError):
            # Испорченная запись не должна запрещать уведомление навсегда.
            return True
        interval = timedelta(seconds=self._config.startup_interval_seconds)
        return now - previous >= interval

    async def _remember_startup(self, now: UtcDatetime) -> None:
        if self._state is None:
            return
        await self._state.set(STARTUP_NOTIFIED_KEY, now.isoformat(), updated_at=now)

    async def _send(self, text: str) -> bool:
        """Отправить сообщение, не позволяя сбою доставки уронить вызвавшего.

        Операционное уведомление — диагностика, а не бизнес-результат: его
        недоставка не должна прерывать запуск или цикл сканирования
        (``CLAUDE.md`` §35).
        """
        try:
            receipt = await self._transport.send(
                OutgoingMessage(destination=self._destination, text=text)
            )
        except MonikError as error:
            _LOGGER.warning(
                "system notification was not delivered",
                extra=log_fields(error_category=error.info.category.value),
            )
            return False
        if not receipt.delivered:
            _LOGGER.warning(
                "system notification was rejected",
                extra=log_fields(
                    error_kind=receipt.error_kind.value if receipt.error_kind else None
                ),
            )
        return receipt.delivered

    def _now(self) -> UtcDatetime:
        return self._clock.now()
