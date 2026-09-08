"""Тексты операционных уведомлений.

Формат сообщений централизован (``15_NOTIFICATION_SYSTEM.md`` §47):
разные подсистемы не создают собственных hard-coded форматов.

В текст попадает только операционное состояние. Ни ключи провайдеров, ни
bot token, ни chat id, ни тела ответов API здесь не появляются
(``19_HEALTH_MONITORING.md`` §65, ``15_NOTIFICATION_SYSTEM.md`` §70-71).
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.health import ApplicationHealthStatus
from monik.domain.enums.notifications import StartupKind, SystemAlertSeverity
from monik.domain.models.health import ApplicationHealth

__all__ = [
    "StartupSummary",
    "aggregated_text",
    "recovery_text",
    "severity_for_component",
    "severity_for_provider",
    "startup_text",
    "transition_text",
]

#: Маркер важности в начале сообщения.
_MARKERS: dict[SystemAlertSeverity, str] = {
    SystemAlertSeverity.INFO: "🟢",
    SystemAlertSeverity.WARNING: "🟠",
    SystemAlertSeverity.CRITICAL: "🔴",
}

#: Заголовок сообщения о запуске для каждого вида запуска.
_STARTUP_HEADLINES: dict[StartupKind, str] = {
    StartupKind.INITIAL: "Monik запущен",
    StartupKind.RESTART: "Monik перезапущен",
    StartupKind.CRASH_RECOVERY: "Monik запущен после аварийного завершения",
}

#: Состояния приложения, при которых запуск считается неполным.
_STARTUP_SUFFIX: dict[ApplicationHealthStatus, str] = {
    ApplicationHealthStatus.DEGRADED: " с предупреждениями",
    ApplicationHealthStatus.UNAVAILABLE: " с критическими ошибками",
}

#: Подсистемы, состояние которых показывается в сообщении о запуске.
_STARTUP_COMPONENTS = ("level1", "level2", "notifications", "database", "scheduler")


@dataclass(frozen=True, slots=True)
class StartupSummary:
    """Данные для сообщения о завершении запуска.

    Собираются composition root'ом из конфигурации и снимка Health
    Monitoring: сама Notification System состояние не вычисляет.
    """

    kind: StartupKind
    version: str
    environment: str
    network: str
    providers: tuple[str, ...]
    health: ApplicationHealth
    recovered: int = 0


def severity_for_provider(status: str) -> SystemAlertSeverity:
    """Важность сообщения о состоянии провайдера."""
    if status in {"healthy", "recovering"}:
        return SystemAlertSeverity.INFO
    if status == "unavailable":
        return SystemAlertSeverity.CRITICAL
    return SystemAlertSeverity.WARNING


def severity_for_component(status: str) -> SystemAlertSeverity:
    """Важность сообщения о состоянии подсистемы."""
    if status == ApplicationHealthStatus.UNAVAILABLE.value:
        return SystemAlertSeverity.CRITICAL
    if status in {
        ApplicationHealthStatus.HEALTHY.value,
        ApplicationHealthStatus.STARTING.value,
        ApplicationHealthStatus.STOPPING.value,
    }:
        return SystemAlertSeverity.INFO
    return SystemAlertSeverity.WARNING


def startup_text(summary: StartupSummary) -> str:
    """Сообщение о завершении запуска.

    Отправляется только после проверки готовности: до неё состояние
    подсистем неизвестно, и объявлять запуск успешным нельзя
    (``19_HEALTH_MONITORING.md`` §70).
    """
    status = summary.health.status
    severity = _startup_severity(status)
    headline = _STARTUP_HEADLINES[summary.kind] + _STARTUP_SUFFIX.get(status, "")
    lines = [
        f"{_MARKERS[severity]} {headline}",
        f"Версия: {summary.version}",
        f"Окружение: {summary.environment}",
        f"Сеть: {summary.network}",
        f"Провайдеры: {', '.join(summary.providers) if summary.providers else 'не настроены'}",
    ]
    lines.extend(_component_lines(summary.health))
    lines.extend(_provider_lines(summary.health))
    if summary.recovered:
        lines.append(f"Восстановлено незавершённых записей: {summary.recovered}")
    lines.append(f"Общее состояние: {status.value}")
    return "\n".join(lines)


def transition_text(
    subject: str, status: str, *, severity: SystemAlertSeverity, reason: str | None = None
) -> str:
    """Сообщение о смене состояния подсистемы или провайдера."""
    text = f"{_MARKERS[severity]} {subject}: {status}"
    if reason:
        return f"{text} ({reason})"
    return text


def recovery_text(subject: str) -> str:
    """Сообщение о восстановлении (``19_HEALTH_MONITORING.md`` §48)."""
    return f"{_MARKERS[SystemAlertSeverity.INFO]} {subject}: восстановлен"


def aggregated_text(subject: str, status: str, *, errors: int) -> str:
    """Периодическое напоминание о незакрытом состоянии.

    Сообщение отправляется не на каждую ошибку, а по накопленному счётчику
    (``28_OBSERVABILITY.md`` §59-60).
    """
    if errors > 0:
        return f"⚠️ {subject}: всё ещё {status} — {errors} ошибок с прошлого уведомления"
    return f"⚠️ {subject}: всё ещё {status}"


def _startup_severity(status: ApplicationHealthStatus) -> SystemAlertSeverity:
    if status is ApplicationHealthStatus.UNAVAILABLE:
        return SystemAlertSeverity.CRITICAL
    if status is ApplicationHealthStatus.DEGRADED:
        return SystemAlertSeverity.WARNING
    return SystemAlertSeverity.INFO


def _component_lines(health: ApplicationHealth) -> list[str]:
    known = {item.component: item.status.value for item in health.components}
    return [
        f"{component}: {known[component]}"
        for component in _STARTUP_COMPONENTS
        if component in known
    ]


def _provider_lines(health: ApplicationHealth) -> list[str]:
    return [f"provider {item.provider_id.value}: {item.status.value}" for item in health.providers]
