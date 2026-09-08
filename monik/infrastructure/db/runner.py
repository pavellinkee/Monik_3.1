"""Применение миграций схемы.

Миграции применяются строго по возрастанию версии; пропуск обязательной
миграции невозможен (``30_DATABASE_SCHEMA.md`` §16). Каждая миграция
выполняется в одной транзакции: при ошибке схема остаётся в предыдущем
состоянии, а запуск приложения прерывается
(``30_DATABASE_SCHEMA.md`` §17-18).
"""

from __future__ import annotations

from datetime import UTC, datetime

from monik.domain.errors import DatabaseError
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.migrations import ALL_MIGRATIONS, Migration
from monik.infrastructure.db.types import to_timestamp
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["MigrationRunner"]

_LOGGER = get_logger("infrastructure.db.migrations")

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


class MigrationRunner:
    """Приводит схему базы данных к актуальной версии."""

    def __init__(
        self,
        database: Database,
        migrations: tuple[Migration, ...] = ALL_MIGRATIONS,
    ) -> None:
        self._database = database
        self._migrations = tuple(sorted(migrations, key=lambda item: item.version))
        self._validate_versions()

    def _validate_versions(self) -> None:
        versions = [migration.version for migration in self._migrations]
        if len(set(versions)) != len(versions):
            raise ValueError("duplicate migration version detected")

    async def applied_versions(self) -> tuple[int, ...]:
        """Версии уже применённых миграций."""
        await self._database.execute(_CREATE_MIGRATIONS_TABLE)
        rows = await self._database.fetch_all(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        return tuple(int(row["version"]) for row in rows)

    async def current_version(self) -> int:
        """Текущая версия схемы (``0`` — база пуста)."""
        applied = await self.applied_versions()
        return applied[-1] if applied else 0

    async def pending(self) -> tuple[Migration, ...]:
        """Миграции, которые ещё не применены."""
        applied = set(await self.applied_versions())
        return tuple(item for item in self._migrations if item.version not in applied)

    async def upgrade(self) -> tuple[int, ...]:
        """Применить все недостающие миграции.

        Возвращает версии, применённые в этом вызове. Повторный запуск на
        актуальной базе ничего не меняет.
        """
        applied = set(await self.applied_versions())
        self._check_for_unknown_versions(applied)

        performed: list[int] = []
        for migration in self._migrations:
            if migration.version in applied:
                continue
            await self._apply(migration)
            performed.append(migration.version)
        return tuple(performed)

    def _check_for_unknown_versions(self, applied: set[int]) -> None:
        """Схема из будущего не поддерживается.

        Продолжать работу с предположительно несовместимой схемой запрещено
        (``30_DATABASE_SCHEMA.md`` §18).
        """
        known = {migration.version for migration in self._migrations}
        unknown = applied - known
        if unknown:
            raise DatabaseError(
                "database contains migrations unknown to this build: "
                + ", ".join(str(version) for version in sorted(unknown)),
                code="database_schema_incompatible",
            )

    async def _apply(self, migration: Migration) -> None:
        _LOGGER.info(
            "applying migration",
            extra=log_fields(version=migration.version, name=migration.name),
        )
        async with self._database.transaction() as connection:
            for statement in migration.statements:
                await connection.execute(statement)
            await connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    to_timestamp(datetime.now(UTC)),
                ),
            )
