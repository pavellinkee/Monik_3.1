"""E2E: запуск приложения, recovery и graceful shutdown.

Порядок запуска — ``CLAUDE.md`` §30. Внешние вызовы не выполняются:
провайдеры и Telegram заменены детерминированными test implementations
после сборки контейнера.
"""

from __future__ import annotations

import asyncio
import copy
import pathlib
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest

from monik.app.lifecycle import (
    TASK_LEVEL1_SCAN,
    TASK_NOTIFICATIONS,
    Application,
    create_application,
)
from monik.config import LoadedConfiguration, parse_configuration
from monik.domain.enums.health import ApplicationHealthStatus, SupervisorState
from monik.domain.enums.lifecycle import (
    JobStatus,
    NotificationStatus,
    OpportunityStatus,
)
from monik.domain.enums.notifications import DestinationKind
from monik.domain.enums.providers import ProviderId
from monik.infrastructure.db import Database
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.infrastructure.providers.fake import FakeAdapter
from monik.infrastructure.telegram import FakeTransport
from monik.services.notifications import NotificationDispatcher
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.level1.conftest import arbitrage_rule, level1_document
from tests.component.notifications.conftest import notification_env
from tests.unit.config.conftest import VALID_ENV


def application_document(**overrides: Any) -> dict[str, Any]:
    """Конфигурация приложения для e2e-запуска.

    Цена газа задана явно (источник ``static``), поэтому запуск не
    обращается к RPC: внешних вызовов в e2e-тестах нет.
    """
    document = copy.deepcopy(level1_document())
    document["gas"] = {
        "sources": ["static"],
        "static_wei_per_gas": {"polygon": 5_000_000_000},
    }
    document["scheduler"] = {
        "tasks": {
            TASK_LEVEL1_SCAN: {"mode": "interval", "interval_seconds": 300},
            TASK_NOTIFICATIONS: {"mode": "interval", "interval_seconds": 10},
        }
    }
    document.update(overrides)
    return document


def loaded_configuration(**overrides: Any) -> LoadedConfiguration:
    return parse_configuration(application_document(**overrides), environ=dict(VALID_ENV))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


def fake_adapters(clock: FakeClock) -> dict[ProviderId, AggregatorAdapter]:
    """Детерминированные адаптеры (``CLAUDE.md`` §10): внешних вызовов нет."""
    return {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }


@pytest.fixture
async def application(
    tmp_path: pathlib.Path, clock: FakeClock
) -> AsyncIterator[tuple[Application, Database]]:
    document = application_document()
    document["database"] = {"path": str(tmp_path / "monik.db")}
    loaded = parse_configuration(document, environ=dict(VALID_ENV))
    app, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    try:
        yield app, database
    finally:
        await app.shutdown()
        await database.close()


# --- запуск ---------------------------------------------------------------


async def test_startup_on_a_clean_database(
    application: tuple[Application, Database],
) -> None:
    """Полный старт на чистой базе (``CLAUDE.md`` §30)."""
    app, database = application

    report = await app.startup()

    assert report.total == 0
    health = app.container.health.application_health()
    assert health.status is ApplicationHealthStatus.HEALTHY
    row = await database.fetch_one("SELECT COUNT(*) AS count FROM schema_migrations", ())
    assert row is not None and row["count"] > 0


async def test_startup_initialises_subsystems(
    application: tuple[Application, Database],
) -> None:
    """Подсистемы получают состояние HEALTHY."""
    app, _ = application
    await app.startup()

    for component in ("configuration", "database", "resource_manager", "scheduler", "level1"):
        health = app.container.health.component(component)
        assert health is not None
        assert health.status is ApplicationHealthStatus.HEALTHY


async def test_scheduler_tick_runs_a_scan(
    application: tuple[Application, Database],
) -> None:
    """Level 1 запускается планировщиком, а не собственным таймером."""
    app, database = application
    await app.startup()

    outcomes = await app.scheduler.tick()

    assert any(item.execution.task_id == TASK_LEVEL1_SCAN for item in outcomes)
    row = await database.fetch_one("SELECT COUNT(*) AS count FROM scans", ())
    assert row is not None and row["count"] == 1


async def test_full_cycle_creates_opportunity_and_notification(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Сквозной цикл: scan → Level 2 → подтверждение → очередь доставки."""
    document = application_document()
    document["database"] = {"path": str(tmp_path / "cycle.db")}
    document["notifications"] = {
        "enabled": True,
        "telegram": {
            "enabled": True,
            "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
            "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
            "commands_enabled": False,
        },
    }
    loaded = parse_configuration(document, environ=notification_env())
    app, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    transport = FakeTransport()
    # Доставка проверяется через тот же store, но с детерминированным
    # транспортом: обращения к Bot API в тестах нет.
    dispatcher = NotificationDispatcher(
        loaded.config.notifications,
        store=app.container.repositories.notifications,
        transports={DestinationKind.TELEGRAM.value: transport},
        clock=clock,
    )
    try:
        await app.startup()
        result = await app.container.level1.scan()
        assert result.opportunities

        confirmations = await app.container.level2_worker.drain()
        assert confirmations and confirmations[0].job_status is JobStatus.CONFIRMED

        outcome = await app.container.opportunities.record_confirmation(
            result.opportunities[0], confirmations[0]
        )
        assert outcome.status is OpportunityStatus.CONFIRMED

        report = await dispatcher.dispatch_pending()
        assert report.delivered
        assert transport.sent and transport.sent[0].details_label == "об"
    finally:
        await app.shutdown()
        await database.close()


# --- recovery -------------------------------------------------------------


async def test_interrupted_job_is_requeued(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """``RUNNING`` после аварии не считается успехом (``CLAUDE.md`` §30)."""
    document = application_document()
    document["database"] = {"path": str(tmp_path / "recovery.db")}
    loaded = parse_configuration(document, environ=dict(VALID_ENV))

    first, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    await first.startup()
    result = await first.container.level1.scan()
    opportunity = result.opportunities[0]
    job = await first.container.repositories.jobs.get_by_opportunity(opportunity.opportunity_id)
    assert job is not None
    await first.container.repositories.jobs.update_status(
        job.k_id, JobStatus.RUNNING, updated_at=clock.now()
    )
    await first.container.level2_worker.cancel_all()
    await database.close()

    # Рестарт на той же базе.
    second, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    try:
        report = await second.startup()

        assert str(job.k_id) in report.requeued_jobs
        restored = await second.container.repositories.jobs.get(job.k_id)
        assert restored is not None and restored.status is JobStatus.QUEUED
    finally:
        await second.shutdown()
        await database.close()


async def test_expired_job_is_not_requeued(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Просроченный Job не возвращается в очередь как актуальный."""
    document = application_document()
    document["database"] = {"path": str(tmp_path / "expired.db")}
    loaded = parse_configuration(document, environ=dict(VALID_ENV))

    first, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    await first.startup()
    result = await first.container.level1.scan()
    job = await first.container.repositories.jobs.get_by_opportunity(
        result.opportunities[0].opportunity_id
    )
    assert job is not None
    await first.container.repositories.jobs.update_status(
        job.k_id, JobStatus.RUNNING, updated_at=clock.now()
    )
    await first.container.level2_worker.cancel_all()
    await database.close()

    clock.advance(timedelta(hours=2))
    second, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    try:
        report = await second.startup()

        assert str(job.k_id) in report.expired_jobs
        restored = await second.container.repositories.jobs.get(job.k_id)
        assert restored is not None and restored.status is JobStatus.EXPIRED
    finally:
        await second.shutdown()
        await database.close()


async def test_interrupted_notification_is_requeued(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Прерванная отправка не считается доставленной (``15`` §61)."""
    document = application_document()
    document["database"] = {"path": str(tmp_path / "notify.db")}
    document["notifications"] = {
        "enabled": True,
        "telegram": {
            "enabled": True,
            "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
            "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
            "commands_enabled": False,
        },
    }
    loaded = parse_configuration(document, environ=notification_env())

    first, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    await first.startup()
    result = await first.container.level1.scan()
    confirmations = await first.container.level2_worker.drain()
    outcome = await first.container.opportunities.record_confirmation(
        result.opportunities[0], confirmations[0]
    )
    notification_id = outcome.notifications[0].notification_id
    await first.container.repositories.notifications.update_delivery_state(
        notification_id, NotificationStatus.SENDING, updated_at=clock.now(), attempt_count=1
    )
    await database.close()

    second, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    try:
        report = await second.startup()

        assert notification_id in report.requeued_notifications
        restored = await second.container.repositories.notifications.get(notification_id)
        assert restored is not None and restored.status is NotificationStatus.QUEUED
    finally:
        await second.shutdown()
        await database.close()


async def test_repeated_startup_creates_no_duplicates(
    application: tuple[Application, Database],
) -> None:
    """Повторный старт не создаёт дублирующих записей."""
    app, database = application
    await app.startup()
    await app.startup()

    row = await database.fetch_one("SELECT COUNT(*) AS count FROM scans", ())
    assert row is not None and row["count"] == 0


# --- shutdown -------------------------------------------------------------


async def test_graceful_shutdown_stops_workers(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Graceful shutdown прекращает создание новых циклов (``14`` §49)."""
    document = application_document()
    document["database"] = {"path": str(tmp_path / "shutdown.db")}
    loaded = parse_configuration(document, environ=dict(VALID_ENV))
    app, database = await create_application(loaded, clock=clock, adapters=fake_adapters(clock))
    await app.startup()

    running = asyncio.ensure_future(app.run())
    await asyncio.sleep(0)
    await app.shutdown()
    state = await running
    await database.close()

    assert state in {SupervisorState.STOPPED, SupervisorState.SAFE_STOP}
    assert app.container.health.application_health().status is ApplicationHealthStatus.STOPPING
