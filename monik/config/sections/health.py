"""Конфигурация Health Monitoring."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection

__all__ = ["HealthConfig"]


class HealthConfig(ConfigSection):
    """Пороги health-состояний (``19_HEALTH_MONITORING.md`` §50-52).

    Отдельные пороги отказа и восстановления образуют гистерезис и
    защищают от постоянного переключения состояний из-за единичных
    transient ошибок (``19_HEALTH_MONITORING.md`` §49).
    """

    enabled: bool = True
    check_interval_seconds: int = Field(default=60, ge=5, le=3600)
    provider_degraded_threshold: int = Field(default=2, ge=1, le=100)
    provider_failure_threshold: int = Field(default=4, ge=1, le=100)
    provider_recovery_threshold: int = Field(default=2, ge=1, le=100)
    worker_restart_limit: int = Field(default=3, ge=0, le=100)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Порог отказа обязан превышать порог деградации.

        Иначе состояние ``DEGRADED`` было бы недостижимо, а провайдер
        переходил бы из ``HEALTHY`` сразу в ``UNAVAILABLE``.
        """
        if self.provider_degraded_threshold > self.provider_failure_threshold:
            raise ValueError(
                "provider_degraded_threshold must not exceed provider_failure_threshold"
            )
        return self
