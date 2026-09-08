"""Состояния health monitoring."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class ApplicationHealthStatus(DomainEnum):
    """Состояние приложения в целом (``35_STATE_MACHINES.md`` §104)."""

    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    STOPPING = "stopping"


class ProviderHealthStatus(DomainEnum):
    """Состояние конкретного provider (``35_STATE_MACHINES.md`` §91).

    ``UNKNOWN`` не означает ``HEALTHY`` (``35_STATE_MACHINES.md`` §92).
    Health не равен capability (``19_HEALTH_MONITORING.md`` §55).
    """

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    RECOVERING = "recovering"


class AdapterState(DomainEnum):
    """Lifecycle состояние Aggregator Adapter (``06_AGGREGATOR_ADAPTERS.md`` §74)."""

    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    FAILED = "failed"
    SHUTTING_DOWN = "shutting_down"


class SupervisorState(DomainEnum):
    """Состояние Supervisor (``42_ARCHITECTURE_MAP.md``).

    ``SAFE_STOP`` — реакция на критическую ошибку persistence
    (``CLAUDE.md`` §34): система прекращает работу, а не продолжает с
    недостоверным состоянием.
    """

    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    SAFE_STOP = "safe_stop"
    STOPPED = "stopped"
