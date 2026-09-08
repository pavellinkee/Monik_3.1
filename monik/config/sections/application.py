"""Общие параметры приложения."""

from __future__ import annotations

from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.base import DomainEnum

__all__ = ["ApplicationConfig", "Environment"]


class Environment(DomainEnum):
    """Окружение запуска.

    Production и test окружения изолированы (``22_SECURITY.md``,
    ``30_DATABASE_SCHEMA.md`` §91-92).
    """

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ApplicationConfig(ConfigSection):
    """Параметры приложения в целом."""

    environment: Environment = Environment.DEVELOPMENT
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    shutdown_timeout_seconds: int = Field(default=30, ge=1, le=600)

    @model_validator(mode="after")
    def _validate_timezone(self) -> Self:
        """Timezone обязана быть валидной IANA-зоной (``17_CONFIGURATION.md`` §19)."""
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"invalid IANA timezone: {self.timezone!r}") from exc
        return self

    @property
    def is_production(self) -> bool:
        """Работает ли приложение в production."""
        return self.environment is Environment.PRODUCTION
