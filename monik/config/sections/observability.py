"""Конфигурация логирования и метрик."""

from __future__ import annotations

from pydantic import Field

from monik.config.base import ConfigSection
from monik.domain.enums.base import DomainEnum

__all__ = ["LogLevel", "LoggingConfig", "MetricsConfig"]


class LogLevel(DomainEnum):
    """Уровень логирования."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LoggingConfig(ConfigSection):
    """Параметры логирования (``17_CONFIGURATION.md`` §48).

    Секреты не выводятся независимо от уровня: редакция встроена в форматтер
    и не управляется конфигурацией.
    """

    level: LogLevel = LogLevel.INFO
    directory: str | None = Field(default="logs", max_length=512)
    retention_days: int = Field(default=14, ge=1, le=365)


class MetricsConfig(ConfigSection):
    """Параметры сбора метрик (``17_CONFIGURATION.md`` §49)."""

    enabled: bool = True
    collection_interval_seconds: int = Field(default=60, ge=1, le=3600)
