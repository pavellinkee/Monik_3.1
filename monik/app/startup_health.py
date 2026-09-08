"""Проверка готовности при запуске и вид запуска.

Приложение не объявляется работоспособным до проверки критических
подсистем и доступности провайдеров (``19_HEALTH_MONITORING.md`` §69-70):
операционное уведомление отправляется только после этой проверки.

Вид запуска (первый запуск, штатный перезапуск, запуск после аварии)
определяется по сохранённой отметке предыдущего процесса: предыдущее
``HEALTHY`` состояние не считается актуальным (§72).

Проверка провайдеров использует health check адаптеров, то есть проходит
через Resource Manager, и не создаёт собственных запросов в обход него
(``19_HEALTH_MONITORING.md`` §75).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from monik.domain.enums.health import AdapterState, ProviderHealthStatus
from monik.domain.enums.notifications import StartupKind
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import MonikError
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.services.health import HealthMonitor
from monik.services.observability.logging import get_logger, log_fields

__all__ = [
    "RUNTIME_STATE_KEY",
    "RuntimeStateStore",
    "detect_startup_kind",
    "mark_running",
    "mark_stopped",
    "probe_providers",
]

_LOGGER = get_logger("app.startup_health")

#: Ключ отметки состояния процесса в ``app_metadata``.
RUNTIME_STATE_KEY = "app.runtime.state"

#: Значение отметки во время работы процесса.
_RUNNING = "running"

#: Значение отметки после graceful shutdown.
_STOPPED = "stopped"

#: Состояние адаптера → состояние провайдера в Health Monitoring.
#: Временная недоступность не означает отсутствие поддержки операции
#: (``19_HEALTH_MONITORING.md`` §55), поэтому capability не изменяется.
_PROBE_STATUSES: dict[AdapterState, ProviderHealthStatus] = {
    AdapterState.READY: ProviderHealthStatus.HEALTHY,
    AdapterState.STARTING: ProviderHealthStatus.UNKNOWN,
    AdapterState.DEGRADED: ProviderHealthStatus.DEGRADED,
    AdapterState.DISABLED: ProviderHealthStatus.UNAVAILABLE,
    AdapterState.FAILED: ProviderHealthStatus.UNAVAILABLE,
    AdapterState.SHUTTING_DOWN: ProviderHealthStatus.UNAVAILABLE,
}


@runtime_checkable
class RuntimeStateStore(Protocol):
    """Хранилище отметки состояния процесса, переживающее рестарт."""

    async def get(self, key: str) -> str | None:
        """Значение по ключу."""
        ...

    async def set(self, key: str, value: str, *, updated_at: datetime) -> None:
        """Записать значение."""
        ...


async def detect_startup_kind(state: RuntimeStateStore) -> StartupKind:
    """Определить, каким является текущий запуск.

    Отметка ``running``, оставшаяся от предыдущего процесса, означает, что
    он не завершился штатно.
    """
    stored = await state.get(RUNTIME_STATE_KEY)
    if stored is None:
        return StartupKind.INITIAL
    if stored == _RUNNING:
        return StartupKind.CRASH_RECOVERY
    return StartupKind.RESTART


async def mark_running(state: RuntimeStateStore, *, now: datetime) -> None:
    """Отметить, что процесс работает."""
    await state.set(RUNTIME_STATE_KEY, _RUNNING, updated_at=now)


async def mark_stopped(state: RuntimeStateStore, *, now: datetime) -> None:
    """Отметить штатное завершение процесса."""
    await state.set(RUNTIME_STATE_KEY, _STOPPED, updated_at=now)


async def probe_providers(
    adapters: dict[ProviderId, AggregatorAdapter],
    *,
    health: HealthMonitor,
) -> None:
    """Проверить доступность провайдеров и записать результат.

    Ошибка проверки не прерывает запуск: недоступный провайдер делает
    приложение ``DEGRADED``, но остальные продолжают работать
    (``19_HEALTH_MONITORING.md`` §12).
    """
    for provider_id, adapter in adapters.items():
        try:
            result = await adapter.health_check()
        except MonikError as error:
            health.record_provider_probe(
                provider_id, ProviderHealthStatus.UNAVAILABLE, reason=error.info.code
            )
            _LOGGER.warning(
                "provider health check failed",
                extra=log_fields(provider=provider_id.value, error_code=error.info.code),
            )
            continue
        health.record_provider_probe(
            provider_id,
            _PROBE_STATUSES.get(result.state, ProviderHealthStatus.UNKNOWN),
            reason=result.detail,
        )
