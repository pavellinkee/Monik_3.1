"""Состояние здоровья подсистем и провайдеров."""

from __future__ import annotations

from pydantic import Field

from monik.domain.enums.health import ApplicationHealthStatus, ProviderHealthStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["ApplicationHealth", "ComponentHealth", "ProviderHealth"]


class ComponentHealth(DomainModel):
    """Состояние отдельной подсистемы (``36_DATA_MODELS.md`` §62)."""

    component: str = Field(min_length=1, max_length=64)
    status: ApplicationHealthStatus
    observed_at: UtcDatetime
    reason: str | None = Field(default=None, max_length=256)


class ProviderHealth(DomainModel):
    """Состояние провайдера (``35_STATE_MACHINES.md`` §91).

    Health не равен capability (``19_HEALTH_MONITORING.md`` §55): временная
    недоступность не означает отсутствие поддержки операции.
    Счётчики нужны для гистерезиса и защиты от flapping
    (``35_STATE_MACHINES.md`` §103).
    """

    provider_id: ProviderId
    status: ProviderHealthStatus
    observed_at: UtcDatetime
    consecutive_failures: int = Field(default=0, ge=0)
    consecutive_successes: int = Field(default=0, ge=0)
    reason: str | None = Field(default=None, max_length=256)


class ApplicationHealth(DomainModel):
    """Сводное состояние приложения (``35_STATE_MACHINES.md`` §104)."""

    status: ApplicationHealthStatus
    observed_at: UtcDatetime
    components: tuple[ComponentHealth, ...] = ()
    providers: tuple[ProviderHealth, ...] = ()
