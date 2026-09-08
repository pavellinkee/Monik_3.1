"""Крах в контрольных точках и восстановление после рестарта.

Контрольные точки (``39_IMPLEMENTATION_PLAN.md`` §55): после создания
Opportunity, после создания Job, во время выполнения Job, после сохранения
confirmation snapshot, во время доставки уведомления и во время повтора.

Общее требование: рестарт не создаёт дублей, а ``RUNNING`` после аварии
никогда не превращается в успех (``35_STATE_MACHINES.md`` §135).
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from monik.app.lifecycle import Application, create_application
from monik.config import LoadedConfiguration, parse_configuration
from monik.domain.enums.lifecycle import (
    JobStatus,
    NotificationStatus,
    OpportunityStatus,
)
from monik.infrastructure.db import Database
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.notifications.conftest import notification_env
from tests.e2e.test_scenarios import (
    PROFITABLE,
    adapters_from,
    scenario_document,
)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


class Runtime:
    """Приложение, которое можно «уронить» и запустить заново на той же базе."""

    def __init__(self, document: dict[str, Any], environ: dict[str, str], clock: FakeClock) -> None:
        self._loaded: LoadedConfiguration = parse_configuration(document, environ=environ)
        self._clock = clock
        self.app: Application | None = None
        self.database: Database | None = None

    async def start(self) -> Application:
        """Запустить приложение (шаги 2-9 ``CLAUDE.md`` §30)."""
        app, database = await create_application(
            self._loaded, clock=self._clock, adapters=adapters_from(PROFITABLE, self._clock)
        )
        await app.startup()
        self.app = app
        self.database = database
        return app

    async def crash(self) -> None:
        """Имитировать аварийную остановку: соединение закрыто без shutdown."""
        if self.app is not None:
            await self.app.container.level2_worker.cancel_all()
        if self.database is not None:
            await self.database.close()
        self.app = None
        self.database = None

    async def stop(self) -> None:
        """Корректно остановить приложение."""
        if self.app is not None:
            await self.app.shutdown()
        if self.database is not None:
            await self.database.close()
        self.app = None
        self.database = None


def runtime(tmp_path: pathlib.Path, clock: FakeClock, *, telegram: bool = False) -> Runtime:
    document = scenario_document(telegram=telegram)
    document.setdefault("database", {})["path"] = str(tmp_path / "crash.db")
    return Runtime(document, notification_env() if telegram else _plain_env(), clock)


def _plain_env() -> dict[str, str]:
    from tests.unit.config.conftest import VALID_ENV

    return dict(VALID_ENV)


async def count(database: Database, table: str) -> int:
    row = await database.fetch_one(f"SELECT COUNT(*) AS count FROM {table}", ())  # noqa: S608
    return int(row["count"]) if row is not None else 0


# --- контрольные точки ----------------------------------------------------


async def test_crash_after_opportunity_creation(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Крах сразу после создания Opportunity не теряет её Job."""
    instance = runtime(tmp_path, clock)
    app = await instance.start()
    result = await app.container.level1.scan()
    opportunity = result.opportunities[0]
    await instance.crash()

    app = await instance.start()
    try:
        assert instance.database is not None
        stored = await app.container.repositories.opportunities.get(opportunity.opportunity_id)
        job = await app.container.repositories.jobs.get_by_opportunity(opportunity.opportunity_id)
        assert stored is not None
        assert job is not None, "Opportunity без Job существовать не может"
        assert await count(instance.database, "opportunities") == 1
        assert await count(instance.database, "level2_jobs") == 1
    finally:
        await instance.stop()


async def test_crash_during_job_execution_does_not_confirm(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """``RUNNING`` после аварии не становится успехом (``35`` §135)."""
    instance = runtime(tmp_path, clock)
    app = await instance.start()
    result = await app.container.level1.scan()
    job = await app.container.repositories.jobs.get_by_opportunity(
        result.opportunities[0].opportunity_id
    )
    assert job is not None
    await app.container.repositories.jobs.update_status(
        job.k_id, JobStatus.RUNNING, updated_at=clock.now()
    )
    await instance.crash()

    app = await instance.start()
    try:
        restored = await app.container.repositories.jobs.get(job.k_id)
        assert restored is not None
        assert restored.status is JobStatus.QUEUED
        assert restored.status is not JobStatus.CONFIRMED
        assert app.recovery_report is not None
        assert str(job.k_id) in app.recovery_report.requeued_jobs
    finally:
        await instance.stop()


async def test_repeated_recovery_is_idempotent(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Повторное восстановление не создаёт дублей."""
    instance = runtime(tmp_path, clock)
    app = await instance.start()
    result = await app.container.level1.scan()
    job = await app.container.repositories.jobs.get_by_opportunity(
        result.opportunities[0].opportunity_id
    )
    assert job is not None
    await app.container.repositories.jobs.update_status(
        job.k_id, JobStatus.RUNNING, updated_at=clock.now()
    )
    await instance.crash()

    app = await instance.start()
    try:
        assert instance.database is not None
        first = await app.recovery.recover()
        second = await app.recovery.recover()

        assert first.requeued_jobs == []  # уже восстановлено при старте
        assert second.requeued_jobs == []
        assert await count(instance.database, "level2_jobs") == 1
        assert await count(instance.database, "opportunities") == 1
    finally:
        await instance.stop()


async def test_crash_after_confirmation_snapshot(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Сохранённый confirmation snapshot переживает рестарт."""
    instance = runtime(tmp_path, clock, telegram=True)
    app = await instance.start()
    result = await app.container.level1.scan()
    confirmations = await app.container.level2_worker.drain()
    outcome = await app.container.opportunities.record_confirmation(
        result.opportunities[0], confirmations[0]
    )
    notification_id = outcome.notifications[0].notification_id
    await instance.crash()

    app = await instance.start()
    try:
        assert instance.database is not None
        stored = await app.container.repositories.opportunities.get(
            result.opportunities[0].opportunity_id
        )
        assert stored is not None
        assert stored.status is OpportunityStatus.CONFIRMED
        saved = await app.container.repositories.jobs.load_confirmation(
            confirmations[0].k_id, confirmations[0].revision
        )
        assert saved is not None
        assert saved.job_status is JobStatus.CONFIRMED
        # Уведомление сохранено ровно одно: дубликатов нет.
        assert await count(instance.database, "notifications") == 1
        restored = await app.container.repositories.notifications.get(notification_id)
        assert restored is not None
        assert restored.status is NotificationStatus.QUEUED
    finally:
        await instance.stop()


async def test_crash_during_notification_delivery(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Прерванная доставка не считается успешной (``15`` §61)."""
    instance = runtime(tmp_path, clock, telegram=True)
    app = await instance.start()
    result = await app.container.level1.scan()
    confirmations = await app.container.level2_worker.drain()
    outcome = await app.container.opportunities.record_confirmation(
        result.opportunities[0], confirmations[0]
    )
    notification_id = outcome.notifications[0].notification_id
    await app.container.repositories.notifications.update_delivery_state(
        notification_id, NotificationStatus.SENDING, updated_at=clock.now(), attempt_count=1
    )
    await instance.crash()

    app = await instance.start()
    try:
        assert instance.database is not None
        restored = await app.container.repositories.notifications.get(notification_id)
        assert restored is not None
        assert restored.status is NotificationStatus.QUEUED
        assert restored.status is not NotificationStatus.SENT
        assert await count(instance.database, "notifications") == 1
    finally:
        await instance.stop()


async def test_sent_notification_is_not_resent_after_restart(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Уже доставленное уведомление рестарт не трогает (``15`` §60)."""
    instance = runtime(tmp_path, clock, telegram=True)
    app = await instance.start()
    result = await app.container.level1.scan()
    confirmations = await app.container.level2_worker.drain()
    outcome = await app.container.opportunities.record_confirmation(
        result.opportunities[0], confirmations[0]
    )
    notification_id = outcome.notifications[0].notification_id
    await app.container.repositories.notifications.update_delivery_state(
        notification_id, NotificationStatus.SENT, updated_at=clock.now(), attempt_count=1
    )
    await instance.crash()

    app = await instance.start()
    try:
        restored = await app.container.repositories.notifications.get(notification_id)
        assert restored is not None
        assert restored.status is NotificationStatus.SENT
        assert app.recovery_report is not None
        assert notification_id not in app.recovery_report.requeued_notifications
    finally:
        await instance.stop()


async def test_restart_does_not_duplicate_scan_state(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Рестарт не создаёт повторных циклов и возможностей."""
    instance = runtime(tmp_path, clock)
    app = await instance.start()
    await app.container.level1.scan()
    await instance.crash()

    app = await instance.start()
    try:
        assert instance.database is not None
        assert await count(instance.database, "scans") == 1
        assert await count(instance.database, "opportunities") == 1
    finally:
        await instance.stop()


async def test_retry_after_restart_starts_a_new_attempt(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Повтор после рестарта — новая попытка того же ``#K``."""
    instance = runtime(tmp_path, clock)
    app = await instance.start()
    result = await app.container.level1.scan()
    confirmations = await app.container.level2_worker.drain()
    first_revision = confirmations[0].revision
    k_id = confirmations[0].k_id
    await instance.crash()

    app = await instance.start()
    try:
        stored = await app.container.repositories.jobs.get(k_id)
        assert stored is not None
        repeated = await app.container.level2.confirm(stored)

        assert repeated.k_id == k_id
        assert repeated.revision == first_revision + 1
        assert result.opportunities[0].opportunity_id == repeated.opportunity_id
    finally:
        await instance.stop()
