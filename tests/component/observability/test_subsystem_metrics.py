"""Подсистемы записывают метрики в общий реестр."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from monik.config import Configuration, parse_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.scheduler import TaskMode
from monik.domain.models.scheduler import SchedulerTask
from monik.infrastructure.db import Database, MigrationRunner
from monik.services.observability import FakeClock, MetricsRegistry, names
from monik.services.scheduler import RegisteredTask, TaskRunner
from tests import factories as f
from tests.component.level1.conftest import build_harness, level1_document
from tests.unit.config.conftest import VALID_ENV


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "metrics.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


def configured() -> Configuration:
    return parse_configuration(level1_document(), environ=dict(VALID_ENV)).config


async def test_level1_records_scan_metrics(database: Database, clock: FakeClock) -> None:
    """Level 1 записывает циклы, запросы и созданные возможности (``28`` §30)."""
    metrics = MetricsRegistry()
    harness = build_harness(configured(), database, clock, metrics=metrics)

    result = await harness.scanner.scan()

    assert metrics.counter(names.LEVEL1_SCANS, status=result.status.value) == 1
    assert metrics.counter(names.LEVEL1_QUOTE_REQUESTS, status="total") > 0
    assert metrics.counter(names.LEVEL1_OPPORTUNITIES, status="created") == 1
    assert metrics.timing(names.LEVEL1_SCAN_SECONDS, status=result.status.value) is not None


async def test_scheduler_records_task_metrics(clock: FakeClock) -> None:
    """Планировщик записывает статус и длительность задач (``28`` §39)."""
    metrics = MetricsRegistry()
    runner = TaskRunner(clock, metrics)

    async def handler() -> None:
        return None

    item = RegisteredTask(
        task=SchedulerTask(
            task_id="level1_scan", mode=TaskMode.INTERVAL, interval=timedelta(seconds=300)
        ),
        handler=handler,
    )
    await runner.run(item, scheduled_for=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    assert metrics.counter(names.SCHEDULER_EXECUTIONS, task="level1_scan", status="success") == 1
    assert metrics.timing(names.SCHEDULER_SECONDS, task="level1_scan") is not None


def test_metric_labels_never_contain_identifiers() -> None:
    """Ни одна подсистема не использует идентификаторы как labels (``28`` §42)."""
    metrics = MetricsRegistry()
    with pytest.raises(ValueError, match="high cardinality"):
        metrics.increment(names.LEVEL2_JOBS, k_id="#K1")
