"""Тесты соединения с SQLite и его обязательных настроек."""

from __future__ import annotations

import pathlib

import pytest

from monik.config.sections.database import DatabaseConfig
from monik.domain.errors import DatabaseError
from monik.infrastructure.db import Database


async def test_creates_database_file(database: Database) -> None:
    assert database.is_connected
    assert database.path.exists()


async def test_creates_parent_directory(tmp_path: pathlib.Path) -> None:
    config = DatabaseConfig(path=str(tmp_path / "nested" / "dir" / "monik.db"))
    instance = Database(config)
    await instance.connect()
    try:
        assert instance.path.exists()
    finally:
        await instance.close()


async def test_foreign_keys_are_enabled(database: Database) -> None:
    """Ссылочная целостность обязательна (30 §21)."""
    assert await database.foreign_keys_enabled()


async def test_wal_mode_is_enabled(database: Database) -> None:
    assert await database.journal_mode() == "wal"


async def test_wal_can_be_disabled_by_configuration(tmp_path: pathlib.Path) -> None:
    config = DatabaseConfig(path=str(tmp_path / "nowal.db"), wal_enabled=False)
    instance = Database(config)
    await instance.connect()
    try:
        assert await instance.journal_mode() != "wal"
    finally:
        await instance.close()


async def test_integrity_check_passes_on_fresh_database(database: Database) -> None:
    await database.check_integrity()


async def test_operations_require_connection(database_config: DatabaseConfig) -> None:
    instance = Database(database_config)
    with pytest.raises(DatabaseError, match="not connected"):
        await instance.fetch_one("SELECT 1")


async def test_connect_is_idempotent(database: Database) -> None:
    await database.connect()
    assert database.is_connected


async def test_close_is_idempotent(database_config: DatabaseConfig) -> None:
    instance = Database(database_config)
    await instance.connect()
    await instance.close()
    await instance.close()
    assert not instance.is_connected


async def test_driver_errors_are_normalized(database: Database) -> None:
    """Исключения драйвера не выходят за пределы infrastructure (38 §82)."""
    with pytest.raises(DatabaseError, match="database operation failed"):
        await database.fetch_one("SELECT * FROM missing_table")


async def test_constraint_violation_is_normalized(migrated: Database) -> None:
    await migrated.execute(
        "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
        ("k", "v", "2026-01-01T00:00:00+00:00"),
    )
    with pytest.raises(DatabaseError, match="integrity constraint"):
        await migrated.execute(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            ("k", "v2", "2026-01-01T00:00:00+00:00"),
        )
