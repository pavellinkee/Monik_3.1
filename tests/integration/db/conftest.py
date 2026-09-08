"""Fixtures для интеграционных тестов базы данных.

Каждый тест получает собственную временную базу: production database
в тестах не используется никогда (``30_DATABASE_SCHEMA.md`` §91-92).
"""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator

import pytest

from monik.config.sections.database import DatabaseConfig
from monik.infrastructure.db import Database, MigrationRunner


@pytest.fixture
def database_config(tmp_path: pathlib.Path) -> DatabaseConfig:
    """Конфигурация БД во временном каталоге теста."""
    return DatabaseConfig(path=str(tmp_path / "test.db"), busy_timeout_seconds=1.0)


@pytest.fixture
async def database(database_config: DatabaseConfig) -> AsyncIterator[Database]:
    """Открытое соединение с пустой временной базой."""
    instance = Database(database_config)
    await instance.connect()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
async def migrated(database: Database) -> Database:
    """База с применённой схемой."""
    await MigrationRunner(database).upgrade()
    return database
