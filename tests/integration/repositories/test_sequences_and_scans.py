"""Тесты последовательностей идентификаторов и хранилища циклов."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from monik.domain.enums.lifecycle import ScanStatus
from monik.domain.models.scan import ScanStatistics
from monik.domain.value_objects.identifiers import KId, VId
from monik.infrastructure.db import Database
from monik.repositories.sqlite import (
    JOB_SEQUENCE,
    OPPORTUNITY_SEQUENCE,
    SqliteIdSequenceRepository,
    SqliteScanRepository,
)
from tests import factories as f

from .conftest import sample_scan


class TestIdSequences:
    async def test_starts_at_one(self, sequences: SqliteIdSequenceRepository) -> None:
        assert await sequences.current_value(OPPORTUNITY_SEQUENCE) == 0
        assert await sequences.next_value(OPPORTUNITY_SEQUENCE) == 1

    async def test_increments_monotonically(self, sequences: SqliteIdSequenceRepository) -> None:
        values = [await sequences.next_value(OPPORTUNITY_SEQUENCE) for _ in range(5)]
        assert values == [1, 2, 3, 4, 5]

    async def test_spaces_are_independent(self, sequences: SqliteIdSequenceRepository) -> None:
        """#V и #K — разные пространства идентификаторов (CLAUDE.md §20)."""
        await sequences.next_value(OPPORTUNITY_SEQUENCE)
        await sequences.next_value(OPPORTUNITY_SEQUENCE)
        assert await sequences.next_value(JOB_SEQUENCE) == 1
        assert await sequences.current_value(OPPORTUNITY_SEQUENCE) == 2

    async def test_survives_reconnect(
        self, sequences: SqliteIdSequenceRepository, database: Database
    ) -> None:
        """Нумерация продолжается после рестарта, а не начинается заново."""
        await sequences.next_value(OPPORTUNITY_SEQUENCE)
        await sequences.next_value(OPPORTUNITY_SEQUENCE)
        await database.close()
        await database.connect()
        assert await SqliteIdSequenceRepository(database).next_value(OPPORTUNITY_SEQUENCE) == 3

    async def test_concurrent_calls_do_not_collide(
        self, sequences: SqliteIdSequenceRepository
    ) -> None:
        results = await asyncio.gather(
            *(sequences.next_value(OPPORTUNITY_SEQUENCE) for _ in range(20))
        )
        assert sorted(results) == list(range(1, 21))

    async def test_produces_valid_public_identifiers(
        self, sequences: SqliteIdSequenceRepository
    ) -> None:
        assert VId.from_sequence(await sequences.next_value(OPPORTUNITY_SEQUENCE)) == "#V1"
        assert KId.from_sequence(await sequences.next_value(JOB_SEQUENCE)) == "#K1"


class TestScanRepository:
    async def test_create_and_get(self, scans: SqliteScanRepository) -> None:
        scan = sample_scan()
        await scans.create(scan)
        loaded = await scans.get(scan.scan_id)
        assert loaded == scan

    async def test_get_missing_returns_none(self, scans: SqliteScanRepository) -> None:
        assert await scans.get(f.ScanId("11111111-1111-4111-8111-111111111111")) is None

    async def test_update_status_and_statistics(self, scans: SqliteScanRepository) -> None:
        scan = sample_scan()
        await scans.create(scan)
        finished = scan.replace(
            status=ScanStatus.COMPLETE.value,
            finished_at=f.NOW + timedelta(seconds=30),
            statistics=ScanStatistics(quote_requests=12, opportunities_created=2).model_dump(),
        )
        await scans.update(finished)
        loaded = await scans.get(scan.scan_id)
        assert loaded is not None
        assert loaded.status is ScanStatus.COMPLETE
        assert loaded.statistics.quote_requests == 12
        assert loaded.statistics.opportunities_created == 2

    async def test_recent_returns_newest_first(self, scans: SqliteScanRepository) -> None:
        first = sample_scan(ScanStatus.COMPLETE)
        second = first.replace(
            scan_id="44444444-4444-4444-8444-444444444444",
            started_at=f.NOW + timedelta(minutes=5),
            finished_at=f.NOW + timedelta(minutes=6),
        )
        await scans.create(first)
        await scans.create(second)
        recent = await scans.recent(limit=10)
        assert [scan.scan_id for scan in recent] == [second.scan_id, first.scan_id]

    async def test_recent_respects_limit(self, scans: SqliteScanRepository) -> None:
        for index in range(3):
            await scans.create(
                sample_scan(ScanStatus.COMPLETE).replace(
                    scan_id=f"4444444{index}-4444-4444-8444-444444444444",
                    started_at=f.NOW + timedelta(minutes=index),
                    finished_at=f.NOW + timedelta(minutes=index, seconds=30),
                )
            )
        assert len(await scans.recent(limit=2)) == 2

    async def test_cleanup_removes_only_finished_scans(self, scans: SqliteScanRepository) -> None:
        """Активные циклы не удаляются cleanup'ом (30 §71)."""
        running = sample_scan()
        finished = sample_scan(ScanStatus.COMPLETE).replace(
            scan_id="44444444-4444-4444-8444-444444444444"
        )
        await scans.create(running)
        await scans.create(finished)
        removed = await scans.delete_finished_before(f.NOW + timedelta(days=1))
        assert removed == 1
        assert await scans.get(running.scan_id) is not None
        assert await scans.get(finished.scan_id) is None

    async def test_cleanup_keeps_recent_scans(self, scans: SqliteScanRepository) -> None:
        finished = sample_scan(ScanStatus.COMPLETE)
        await scans.create(finished)
        assert await scans.delete_finished_before(f.NOW - timedelta(days=1)) == 0
        assert await scans.get(finished.scan_id) is not None
