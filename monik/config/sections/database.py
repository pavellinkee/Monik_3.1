"""Конфигурация базы данных."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection

__all__ = ["DatabaseConfig", "RetentionConfig"]


class RetentionConfig(ConfigSection):
    """Сроки хранения исторических данных (``31_DATA_RETENTION.md``).

    Ни одна историческая таблица не растёт бесконечно
    (``30_DATABASE_SCHEMA.md`` §69).
    """

    opportunities_days: int = Field(default=90, ge=1, le=3650)
    jobs_days: int = Field(default=30, ge=1, le=3650)
    notifications_days: int = Field(default=30, ge=1, le=3650)
    scans_days: int = Field(default=14, ge=1, le=3650)
    fee_snapshots_days: int = Field(default=30, ge=1, le=3650)


class DatabaseConfig(ConfigSection):
    """Параметры SQLite (``17_CONFIGURATION.md`` §47).

    Путь задаётся конфигурацией и не зашивается в business logic
    (``30_DATABASE_SCHEMA.md`` §90).
    """

    path: str = Field(default="data/monik.db", min_length=1, max_length=512)
    wal_enabled: bool = True
    busy_timeout_seconds: float = Field(default=5.0, gt=0, le=120)
    foreign_keys_enabled: bool = True
    integrity_check_on_startup: bool = True
    backup_enabled: bool = False
    backup_directory: str | None = Field(default=None, max_length=512)
    cleanup_enabled: bool = True
    retention: RetentionConfig = RetentionConfig()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Ключевые защиты БД отключать нельзя."""
        if not self.foreign_keys_enabled:
            raise ValueError(
                "foreign_keys_enabled must remain true: referential integrity is required"
            )
        if self.backup_enabled and not self.backup_directory:
            raise ValueError("backup_enabled requires backup_directory")
        if ".." in self.path.split("/"):
            raise ValueError("database path must not contain parent directory traversal")
        return self
