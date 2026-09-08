"""Тесты транзакций и защиты схемы."""

from __future__ import annotations

from decimal import Decimal

import pytest

from monik.domain.errors import DatabaseError
from monik.infrastructure.db import Database, TransactionManager
from monik.infrastructure.db.types import (
    from_decimal,
    from_raw_amount,
    from_timestamp,
    to_decimal,
    to_raw_amount,
    to_timestamp,
)
from tests import factories as f

_SCAN = ("scan-1", "complete", "{}", "{}", "2026-01-01T12:00:00+00:00", None)


async def _insert_scan(database: Database) -> None:
    await database.execute(
        "INSERT INTO scans (scan_id, status, scope_json, statistics_json, started_at, "
        "finished_at) VALUES (?, ?, ?, ?, ?, ?)",
        _SCAN,
    )


class TestTransactions:
    async def test_commits_on_success(self, migrated: Database) -> None:
        manager = TransactionManager(migrated)
        async with manager.begin() as tx:
            await tx.execute(
                "INSERT INTO scans (scan_id, status, scope_json, statistics_json, started_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("scan-1", "running", "{}", "{}", "2026-01-01T12:00:00+00:00"),
            )
        row = await migrated.fetch_one("SELECT scan_id FROM scans")
        assert row is not None

    async def test_rolls_back_on_exception(self, migrated: Database) -> None:
        manager = TransactionManager(migrated)
        with pytest.raises(RuntimeError):
            async with manager.begin() as tx:
                await tx.execute(
                    "INSERT INTO scans (scan_id, status, scope_json, statistics_json, "
                    "started_at) VALUES (?, ?, ?, ?, ?)",
                    ("scan-1", "running", "{}", "{}", "2026-01-01T12:00:00+00:00"),
                )
                raise RuntimeError("boom")
        assert await migrated.fetch_one("SELECT scan_id FROM scans") is None

    async def test_rolls_back_all_statements(self, migrated: Database) -> None:
        """Атомарность многошаговой записи (CLAUDE.md §29)."""
        manager = TransactionManager(migrated)
        with pytest.raises(DatabaseError):
            async with manager.begin() as tx:
                await tx.execute(
                    "INSERT INTO scans (scan_id, status, scope_json, statistics_json, "
                    "started_at) VALUES (?, ?, ?, ?, ?)",
                    ("scan-1", "running", "{}", "{}", "2026-01-01T12:00:00+00:00"),
                )
                await tx.execute("INSERT INTO scans (scan_id) VALUES ('scan-2')")
        assert await migrated.fetch_all("SELECT scan_id FROM scans") == []

    async def test_driver_errors_inside_transaction_are_normalized(
        self, migrated: Database
    ) -> None:
        manager = TransactionManager(migrated)
        with pytest.raises(DatabaseError):
            async with manager.begin() as tx:
                await tx.fetch_one("SELECT * FROM missing_table")

    async def test_reads_uncommitted_data_inside_same_transaction(self, migrated: Database) -> None:
        manager = TransactionManager(migrated)
        async with manager.begin() as tx:
            await tx.execute(
                "INSERT INTO scans (scan_id, status, scope_json, statistics_json, started_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("scan-1", "running", "{}", "{}", "2026-01-01T12:00:00+00:00"),
            )
            row = await tx.fetch_one("SELECT scan_id FROM scans")
            assert row is not None


class TestConstraints:
    async def test_foreign_key_is_enforced(self, migrated: Database) -> None:
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await migrated.execute(
                "INSERT INTO level2_jobs (k_id, opportunity_id, status, priority, created_at, "
                "updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "#K1",
                    "missing-opportunity",
                    "queued",
                    "level2",
                    "2026-01-01T12:00:00+00:00",
                    "2026-01-01T12:00:00+00:00",
                    "2026-01-01T12:05:00+00:00",
                ),
            )

    async def test_one_job_per_opportunity(self, migrated: Database) -> None:
        """Дедупликация Level 2 workflow (CLAUDE.md §19)."""
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        await self._insert_job(migrated, "#K1")
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await self._insert_job(migrated, "#K2")

    async def test_notification_is_unique_per_destination(self, migrated: Database) -> None:
        """Одна logical notification на destination (30 §41)."""
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        await self._insert_notification(migrated, "n1")
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await self._insert_notification(migrated, "n2")

    async def test_opportunity_amounts_cascade_on_delete(self, migrated: Database) -> None:
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        await migrated.execute(
            "INSERT INTO opportunity_amounts (opportunity_id, raw_input_amount, input_decimals, "
            "preliminary_buy_output, preliminary_sell_output, preliminary_status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("opp-1", "100000000", 6, "5140000000000000000", "101500000", "complete"),
        )
        await migrated.execute("DELETE FROM opportunities WHERE opportunity_id = 'opp-1'")
        assert await migrated.fetch_all("SELECT * FROM opportunity_amounts") == []

    async def test_opportunity_with_notification_cannot_be_deleted(
        self, migrated: Database
    ) -> None:
        """Confirmed opportunity не удаляется обычным cleanup (30 §71, §100.6)."""
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        await self._insert_notification(migrated, "n1")
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await migrated.execute("DELETE FROM opportunities WHERE opportunity_id = 'opp-1'")

    async def test_scan_deletion_keeps_opportunity(self, migrated: Database) -> None:
        """Retention scan'ов короче, чем у opportunities (31)."""
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        await migrated.execute("DELETE FROM scans WHERE scan_id = 'scan-1'")
        row = await migrated.fetch_one(
            "SELECT scan_id FROM opportunities WHERE opportunity_id = 'opp-1'"
        )
        assert row is not None
        assert row["scan_id"] is None

    async def test_v_id_is_unique(self, migrated: Database) -> None:
        await _insert_scan(migrated)
        await self._insert_opportunity(migrated)
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await self._insert_opportunity(migrated, opportunity_id="opp-2")

    @staticmethod
    async def _insert_opportunity(
        database: Database, opportunity_id: str = "opp-1", v_id: str = "#V1"
    ) -> None:
        await database.execute(
            "INSERT INTO opportunities (opportunity_id, v_id, scan_id, status, fingerprint, "
            "network_id, input_token, intermediate_token, output_token, buy_provider_id, "
            "sell_provider_id, buy_route_json, sell_route_json, buy_route_fingerprint, "
            "sell_route_fingerprint, detected_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                opportunity_id,
                v_id,
                "scan-1",
                "created",
                "fp",
                "polygon",
                "polygon:0xa",
                "polygon:0xb",
                "polygon:0xa",
                "oneinch",
                "zero_x",
                "{}",
                "{}",
                "bfp",
                "sfp",
                "2026-01-01T12:00:00+00:00",
                "2026-01-01T12:05:00+00:00",
            ),
        )

    @staticmethod
    async def _insert_job(database: Database, k_id: str) -> None:
        await database.execute(
            "INSERT INTO level2_jobs (k_id, opportunity_id, status, priority, created_at, "
            "updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                k_id,
                "opp-1",
                "queued",
                "level2",
                "2026-01-01T12:00:00+00:00",
                "2026-01-01T12:00:00+00:00",
                "2026-01-01T12:05:00+00:00",
            ),
        )

    @staticmethod
    async def _insert_notification(database: Database, notification_id: str) -> None:
        await database.execute(
            "INSERT INTO notifications (notification_id, opportunity_id, destination_id, "
            "destination_kind, mode, status, sequence, fingerprint, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                notification_id,
                "opp-1",
                "main-chat",
                "telegram",
                "A",
                "queued",
                1,
                "nfp",
                "2026-01-01T12:00:00+00:00",
                "2026-01-01T12:00:00+00:00",
            ),
        )


class TestStorageTypes:
    async def test_decimal_round_trip_preserves_precision(self, migrated: Database) -> None:
        """Decimal хранится как TEXT без потери точности (30 §56)."""
        value = Decimal("1234.567890123456789012345678")
        await migrated.execute(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            ("amount", to_decimal(value), to_timestamp(f.NOW)),
        )
        row = await migrated.fetch_one("SELECT value FROM app_metadata WHERE key = 'amount'")
        assert row is not None
        assert from_decimal(str(row["value"])) == value

    async def test_large_raw_amount_round_trip(self, migrated: Database) -> None:
        """Raw amount 18-decimals токена превышает диапазон INTEGER SQLite."""
        raw = 12_345 * 10**18
        assert raw > 2**63 - 1
        await migrated.execute(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            ("raw", to_raw_amount(raw), to_timestamp(f.NOW)),
        )
        row = await migrated.fetch_one("SELECT value FROM app_metadata WHERE key = 'raw'")
        assert row is not None
        assert from_raw_amount(str(row["value"])) == raw

    async def test_timestamp_round_trip_is_utc(self, migrated: Database) -> None:
        await migrated.execute(
            "INSERT INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?)",
            ("ts", to_timestamp(f.NOW), to_timestamp(f.NOW)),
        )
        row = await migrated.fetch_one("SELECT value FROM app_metadata WHERE key = 'ts'")
        assert row is not None
        restored = from_timestamp(str(row["value"]))
        assert restored == f.NOW
        assert restored.utcoffset() is not None

    async def test_timestamps_sort_lexicographically(self, migrated: Database) -> None:
        earlier = to_timestamp(f.NOW)
        later = to_timestamp(f.NOW.replace(hour=13))
        assert earlier < later

    def test_raw_amount_rejects_non_integer(self) -> None:
        with pytest.raises(TypeError):
            to_raw_amount(True)  # type: ignore[arg-type]
