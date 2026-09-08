"""Тесты миграций и итоговой схемы."""

from __future__ import annotations

import pytest

from monik.domain.errors import DatabaseError
from monik.infrastructure.db import ALL_MIGRATIONS, Database, Migration, MigrationRunner

EXPECTED_TABLES = {
    "app_metadata",
    "capabilities",
    "fee_records",
    "fee_snapshots",
    "gas_snapshots",
    "id_sequences",
    "level2_amount_results",
    "level2_attempts",
    "level2_jobs",
    "notification_attempts",
    "notifications",
    "opportunities",
    "opportunity_amounts",
    "scans",
    "scheduler_executions",
    "scheduler_tasks",
    "schema_migrations",
    "state_transitions",
}


async def _tables(database: Database) -> set[str]:
    rows = await database.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row["name"]) for row in rows if not str(row["name"]).startswith("sqlite_")}


async def _columns(database: Database, table: str) -> set[str]:
    rows = await database.fetch_all(f"PRAGMA table_info({table})")
    return {str(row["name"]) for row in rows}


async def _indexes(database: Database) -> set[str]:
    rows = await database.fetch_all("SELECT name FROM sqlite_master WHERE type = 'index'")
    return {str(row["name"]) for row in rows if str(row["name"]).startswith("idx_")}


class TestFreshDatabase:
    async def test_creates_all_tables(self, database: Database) -> None:
        await MigrationRunner(database).upgrade()
        assert await _tables(database) == EXPECTED_TABLES

    async def test_records_applied_version(self, database: Database) -> None:
        runner = MigrationRunner(database)
        applied = await runner.upgrade()
        expected = tuple(migration.version for migration in ALL_MIGRATIONS)
        assert applied == expected
        assert await runner.current_version() == expected[-1]

    async def test_confirmation_snapshot_columns_exist(self, database: Database) -> None:
        """Миграция 0002 добавляет колонки для восстановления снимков."""
        await MigrationRunner(database).upgrade()
        amounts = await _columns(database, "opportunity_amounts")
        results = await _columns(database, "level2_amount_results")
        assert "preliminary_result_json" in amounts
        assert {"buy_quote_json", "sell_quote_json"} <= results

    async def test_creates_expected_indexes(self, database: Database) -> None:
        await MigrationRunner(database).upgrade()
        indexes = await _indexes(database)
        assert "idx_opportunities_fingerprint" in indexes
        assert "idx_notifications_order" in indexes
        assert "idx_level2_jobs_status" in indexes
        assert "idx_capabilities_lookup" in indexes


class TestIdempotency:
    async def test_second_upgrade_applies_nothing(self, database: Database) -> None:
        runner = MigrationRunner(database)
        await runner.upgrade()
        assert await runner.upgrade() == ()

    async def test_pending_is_empty_after_upgrade(self, database: Database) -> None:
        runner = MigrationRunner(database)
        await runner.upgrade()
        assert await runner.pending() == ()

    async def test_current_version_is_zero_on_empty_database(self, database: Database) -> None:
        assert await MigrationRunner(database).current_version() == 0


class TestMigrationSafety:
    async def test_failed_migration_leaves_schema_unchanged(self, database: Database) -> None:
        """Ошибка миграции не оставляет частично применённую схему (30 §17-18)."""
        broken = Migration(
            version=1,
            name="broken",
            statements=(
                "CREATE TABLE good_table (id TEXT PRIMARY KEY)",
                "CREATE TABLE bad_table (",
            ),
        )
        runner = MigrationRunner(database, (broken,))
        with pytest.raises(DatabaseError):
            await runner.upgrade()
        assert "good_table" not in await _tables(database)
        assert await runner.current_version() == 0

    async def test_unknown_applied_version_stops_startup(self, database: Database) -> None:
        """Схема из будущего несовместима с текущей сборкой (30 §18)."""
        await MigrationRunner(database).upgrade()
        await database.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (999, "from_the_future", "2026-01-01T00:00:00+00:00"),
        )
        with pytest.raises(DatabaseError, match="unknown to this build"):
            await MigrationRunner(database).upgrade()

    async def test_migrations_are_applied_in_order(self, database: Database) -> None:
        first = Migration(version=1, name="first", statements=("CREATE TABLE t1 (id TEXT)",))
        second = Migration(
            version=2,
            name="second",
            statements=("CREATE TABLE t2 (id TEXT REFERENCES t1 (id))",),
        )
        applied = await MigrationRunner(database, (second, first)).upgrade()
        assert applied == (1, 2)

    def test_duplicate_versions_are_rejected(self, database: Database) -> None:
        first = Migration(version=1, name="a", statements=("SELECT 1",))
        second = Migration(version=1, name="b", statements=("SELECT 1",))
        with pytest.raises(ValueError, match="duplicate migration version"):
            MigrationRunner(database, (first, second))

    def test_migration_requires_statements(self) -> None:
        with pytest.raises(ValueError, match="no statements"):
            Migration(version=1, name="empty", statements=())

    def test_migration_version_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            Migration(version=0, name="zero", statements=("SELECT 1",))

    def test_shipped_migrations_have_unique_increasing_versions(self) -> None:
        versions = [migration.version for migration in ALL_MIGRATIONS]
        assert versions == sorted(set(versions))
