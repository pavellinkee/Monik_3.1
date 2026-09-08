"""Хранилище небольших операционных значений приложения.

Используется для состояния, которое обязано пережить рестарт, но не
является доменной сущностью: например offset входящих Telegram-обновлений
(``30_DATABASE_SCHEMA.md``: ``app_metadata``).
"""

from __future__ import annotations

from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import to_timestamp
from monik.repositories.sqlite.mapping import column

__all__ = ["SqliteMetadataRepository"]


class SqliteMetadataRepository:
    """Простое key-value хранилище операционного состояния."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self, key: str) -> str | None:
        """Значение по ключу либо ``None``."""
        row = await self._database.fetch_one("SELECT value FROM app_metadata WHERE key = ?", (key,))
        return str(column(row, "value")) if row is not None else None

    async def set(self, key: str, value: str, *, updated_at: UtcDatetime) -> None:
        """Записать значение, заменив предыдущее."""
        await self._database.execute(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value, to_timestamp(updated_at)),
        )
