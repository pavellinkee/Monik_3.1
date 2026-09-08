"""Fixtures для интеграционных тестов репозиториев."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator

import pytest

from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.lifecycle import ScanStatus
from monik.domain.models.scan import Scan, ScanScope
from monik.infrastructure.db import Database, MigrationRunner
from monik.repositories.sqlite import (
    SqliteIdSequenceRepository,
    SqliteJobRepository,
    SqliteOpportunityRepository,
    SqliteScanRepository,
)
from tests import factories as f


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    """Временная база с применённой схемой."""
    instance = Database(DatabaseConfig(path=str(tmp_path / "repo.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def scans(database: Database) -> SqliteScanRepository:
    return SqliteScanRepository(database)


@pytest.fixture
def opportunities(database: Database) -> SqliteOpportunityRepository:
    return SqliteOpportunityRepository(database)


@pytest.fixture
def jobs(database: Database) -> SqliteJobRepository:
    return SqliteJobRepository(database)


@pytest.fixture
def sequences(database: Database) -> SqliteIdSequenceRepository:
    return SqliteIdSequenceRepository(database)


def sample_scan(status: ScanStatus = ScanStatus.RUNNING) -> Scan:
    """Цикл Level 1 с тем же scan_id, что используют фабрики."""
    return Scan(
        scan_id=f.ScanId("33333333-3333-4333-8333-333333333333"),
        status=status,
        scope=ScanScope(
            networks=(f.POLYGON,),
            providers=(f.ProviderId.ONEINCH, f.ProviderId.ZERO_X),
            tokens=(f.AAVE.key,),
            raw_amounts=(100_000_000,),
        ),
        started_at=f.NOW,
        finished_at=None if status is ScanStatus.RUNNING else f.NOW,
    )


@pytest.fixture
async def stored_scan(scans: SqliteScanRepository) -> Scan:
    """Сохранённый цикл, на который ссылаются возможности."""
    scan = sample_scan()
    await scans.create(scan)
    return scan
