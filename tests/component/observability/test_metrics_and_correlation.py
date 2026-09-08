"""Observability: метрики, correlation context и события переходов."""

from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.lifecycle import JobStatus, OpportunityStatus, ScanStatus
from monik.domain.enums.providers import ProviderId
from monik.infrastructure.db import Database, MigrationRunner
from monik.repositories.sqlite import SqliteStateTransitionRepository
from monik.services.observability import (
    FakeClock,
    MetricsRegistry,
    SecretRegistry,
    StructuredFormatter,
    TransitionRecorder,
    current_context,
    log_context,
    log_fields,
    names,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "obs.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


# --- метрики --------------------------------------------------------------


def test_counters_accumulate() -> None:
    metrics = MetricsRegistry()
    metrics.increment(names.LEVEL1_SCANS, status="complete")
    metrics.increment(names.LEVEL1_SCANS, status="complete")
    metrics.increment(names.LEVEL1_SCANS, status="partial")

    assert metrics.counter(names.LEVEL1_SCANS, status="complete") == 2
    assert metrics.counter(names.LEVEL1_SCANS, status="partial") == 1
    assert metrics.counter(names.LEVEL1_SCANS, status="failed") == 0


def test_timings_are_aggregated() -> None:
    metrics = MetricsRegistry()
    metrics.observe(names.LEVEL2_SECONDS, 0.5, status="confirmed")
    metrics.observe(names.LEVEL2_SECONDS, 1.5, status="confirmed")

    stats = metrics.timing(names.LEVEL2_SECONDS, status="confirmed")
    assert stats is not None
    assert stats.count == 2
    assert stats.total_seconds == 2.0
    assert stats.min_seconds == 0.5
    assert stats.max_seconds == 1.5
    assert stats.average_seconds == 1.0


def test_label_order_does_not_matter() -> None:
    metrics = MetricsRegistry()
    metrics.increment(names.LEVEL1_QUOTE_REQUESTS, provider="oneinch", network="polygon")
    metrics.increment(names.LEVEL1_QUOTE_REQUESTS, network="polygon", provider="oneinch")

    assert metrics.counter(names.LEVEL1_QUOTE_REQUESTS, provider="oneinch", network="polygon") == 2


@pytest.mark.parametrize(
    "label", ["opportunity_id", "k_id", "v_id", "request_id", "address", "url"]
)
def test_high_cardinality_labels_are_rejected(label: str) -> None:
    """Идентификаторы не должны попадать в labels (``28`` §42)."""
    metrics = MetricsRegistry()
    with pytest.raises(ValueError, match="high cardinality"):
        metrics.increment(names.LEVEL2_JOBS, **{label: "value"})


def test_unknown_label_is_rejected() -> None:
    """Набор labels ограничен и предсказуем (``28`` §41)."""
    metrics = MetricsRegistry()
    with pytest.raises(ValueError, match="not allowed"):
        metrics.increment(names.LEVEL2_JOBS, custom="value")


def test_secret_value_is_rejected_in_labels() -> None:
    """Секрет не может попасть в метрику (``28`` §43)."""
    secrets = SecretRegistry()
    secrets.register("super-secret-api-key-value")
    metrics = MetricsRegistry(secrets=secrets)

    with pytest.raises(ValueError, match="secret"):
        metrics.increment(names.LEVEL1_QUOTE_REQUESTS, provider="super-secret-api-key-value")


def test_long_label_value_is_rejected() -> None:
    metrics = MetricsRegistry()
    with pytest.raises(ValueError, match="too long"):
        metrics.increment(names.LEVEL2_JOBS, status="x" * 100)


def test_samples_are_deterministic() -> None:
    metrics = MetricsRegistry()
    metrics.increment(names.LEVEL1_SCANS, status="complete")
    metrics.set_gauge(names.QUEUE_DEPTH, 3, component="level2")
    metrics.observe(names.LEVEL1_SCAN_SECONDS, 2.0, status="complete")

    first = metrics.samples()
    second = metrics.samples()
    assert first == second
    assert [sample.name for sample in first] == sorted(sample.name for sample in first)


# --- correlation context --------------------------------------------------


def test_correlation_context_is_propagated() -> None:
    """Контекст распространяется по вложенным вызовам (``28`` §25)."""
    with log_context(scan_id="scan-1"):
        assert current_context().scan_id == "scan-1"
        with log_context(v_id="#V1", k_id="#K1"):
            context = current_context()
            assert context.scan_id == "scan-1"
            assert context.v_id == "#V1"
            assert context.k_id == "#K1"
        assert current_context().k_id is None
    assert current_context().scan_id is None


def test_log_record_contains_required_fields() -> None:
    """Structured log содержит обязательные поля (``28`` §5)."""
    formatter = StructuredFormatter()
    with log_context(
        scan_id="scan-1",
        v_id="#V1",
        k_id="#K1",
        request_id="req-1",
        provider="oneinch",
        network="polygon",
        operation="buy",
    ):
        record = logging.LogRecord(
            name="monik.services.level1",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="quote received",
            args=(),
            exc_info=None,
        )
        record.__dict__.update(log_fields(duration_seconds=0.25))
        rendered = json.loads(formatter.format(record))

    for field in ("scan_id", "v_id", "k_id", "request_id", "provider", "network", "operation"):
        assert field in rendered
    assert rendered["duration_seconds"] == 0.25
    assert rendered["level"] == "INFO"


# --- события переходов ----------------------------------------------------


async def test_transition_is_recorded_with_correlation(
    database: Database, clock: FakeClock
) -> None:
    """Переход состояния наблюдаем и связан с workflow (``35`` §118)."""
    repository = SqliteStateTransitionRepository(database)
    recorder = TransitionRecorder(repository, clock)

    with log_context(correlation_id="corr-1"):
        await recorder.record(
            entity_type="opportunity",
            entity_id="#V1",
            from_state=OpportunityStatus.CREATED,
            to_state=OpportunityStatus.CONFIRMED,
            reason="level2_confirmed",
        )

    history = await repository.history("opportunity", "#V1")
    assert len(history) == 1
    assert history[0].from_state == "created"
    assert history[0].to_state == "confirmed"
    assert history[0].correlation_id == "corr-1"
    assert history[0].occurred_at == NOW


async def test_transition_works_without_a_log(clock: FakeClock) -> None:
    """Отсутствие журнала не мешает зафиксировать переход в логах."""
    recorder = TransitionRecorder(None, clock)

    transition = await recorder.record(
        entity_type="job",
        entity_id="#K1",
        from_state=JobStatus.QUEUED,
        to_state=JobStatus.RUNNING,
        reason="worker_started",
    )

    assert transition.to_state == "running"


async def test_transition_accepts_plain_strings(clock: FakeClock) -> None:
    recorder = TransitionRecorder(None, clock)

    transition = await recorder.record(
        entity_type="scan",
        entity_id="scan-1",
        to_state=ScanStatus.COMPLETE,
        reason="finished",
    )

    assert transition.from_state is None
    assert transition.to_state == "complete"


def test_provider_label_is_low_cardinality() -> None:
    """Провайдер — допустимый label (``28`` §44)."""
    metrics = MetricsRegistry()
    metrics.observe(names.PROVIDER_LATENCY_SECONDS, 0.2, provider=ProviderId.ONEINCH.value)

    stats = metrics.timing(names.PROVIDER_LATENCY_SECONDS, provider="oneinch")
    assert stats is not None and stats.count == 1


def test_reset_clears_metrics() -> None:
    metrics = MetricsRegistry()
    metrics.increment(names.LEVEL1_SCANS, status="complete")
    metrics.reset()

    assert metrics.samples() == ()
    assert metrics.counter(names.LEVEL1_SCANS, status="complete") == 0


def test_timedelta_observation_is_supported() -> None:
    """Длительности измеряются в секундах."""
    metrics = MetricsRegistry()
    metrics.observe(names.LEVEL1_SCAN_SECONDS, timedelta(seconds=3).total_seconds())

    stats = metrics.timing(names.LEVEL1_SCAN_SECONDS)
    assert stats is not None and stats.total_seconds == 3.0
