"""Telegram commands: разбор, ответы из сохранённых данных и изоляция.

``CLAUDE.md`` §36 — набор команд; §35 — ответ формируется без новых
внешних запросов и не блокирует Scanner.
"""

from __future__ import annotations

import asyncio
import pathlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.lifecycle import JobStatus
from monik.domain.enums.notifications import DestinationKind
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.telegram import FakeTransport
from monik.infrastructure.telegram.polling import TelegramUpdate
from monik.repositories.sqlite import (
    SqliteJobRepository,
    SqliteMetadataRepository,
    SqliteNotificationRepository,
)
from monik.services.commands import (
    OFFSET_KEY,
    CommandName,
    CommandRouter,
    CommandService,
    ComponentStatus,
    StatsSnapshot,
    parse_callback,
    parse_command,
)
from monik.services.observability import FakeClock
from monik.services.opportunity import ConfirmationStatistics
from tests import factories as f
from tests.component.notifications.conftest import (
    NotificationHarness,
    build_notifications,
)

DESTINATION = NotificationDestination(destination_id="chat-main", kind=DestinationKind.TELEGRAM)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(
        DatabaseConfig(path=str(tmp_path / "commands.db"), busy_timeout_seconds=1.0)
    )
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


class StaticStatus:
    """Снимок состояния подсистем для ``/status``."""

    def __init__(self, components: tuple[ComponentStatus, ...] = ()) -> None:
        self._components = components or (
            ComponentStatus(name="level1", state="running"),
            ComponentStatus(name="level2", state="running", detail="0 active"),
        )

    def components(self) -> tuple[ComponentStatus, ...]:
        return self._components


class StaticStats:
    """Статистика для ``/stats``."""

    def __init__(self, snapshot: StatsSnapshot | None = None) -> None:
        self._snapshot = snapshot or StatsSnapshot(
            confirmations=ConfirmationStatistics(confirmed=3, unconfirmed=1, partial=2),
            scans_completed=7,
            opportunities_created=4,
            notifications_sent=3,
        )

    def snapshot(self) -> StatsSnapshot:
        return self._snapshot


@dataclass
class FakeUpdates:
    """Источник обновлений без сети."""

    batches: list[tuple[TelegramUpdate, ...]] = field(default_factory=list)
    offsets: list[int | None] = field(default_factory=list)
    answered: list[str] = field(default_factory=list)

    async def fetch(self, *, offset: int | None, limit: int = 20) -> tuple[TelegramUpdate, ...]:
        self.offsets.append(offset)
        return self.batches.pop(0) if self.batches else ()

    async def answer_callback(self, callback_query_id: str, *, text: str | None = None) -> None:
        self.answered.append(callback_query_id)


async def build_router(
    harness: NotificationHarness, database: Database, **overrides: object
) -> CommandRouter:
    return CommandRouter(
        jobs=SqliteJobRepository(database),
        notifications=SqliteNotificationRepository(database),
        status=overrides.get("status") or StaticStatus(),  # type: ignore[arg-type]
        stats=overrides.get("stats") or StaticStats(),  # type: ignore[arg-type]
    )


# --- разбор ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/level2", CommandName.LEVEL2),
        ("/status", CommandName.STATUS),
        ("/stats", CommandName.STATS),
        ("/details K1234", CommandName.DETAILS),
        ("/status@monik_bot", CommandName.STATUS),
    ],
)
def test_supported_commands_are_parsed(text: str, expected: CommandName) -> None:
    """Поддерживаются все команды ``CLAUDE.md`` §36."""
    command = parse_command(text)
    assert command.name is expected
    assert command.is_valid


def test_details_without_argument_is_reported() -> None:
    command = parse_command("/details")
    assert command.name is CommandName.DETAILS
    assert command.error is not None


def test_unknown_command_is_not_an_error() -> None:
    """Некорректный ввод не ломает подсистему."""
    command = parse_command("/unknown")
    assert command.name is CommandName.UNKNOWN
    assert command.error is not None


def test_plain_text_is_not_a_command() -> None:
    assert parse_command("привет").name is CommandName.UNKNOWN


def test_callback_data_is_parsed() -> None:
    assert parse_callback("details:abc-123") == "abc-123"
    assert parse_callback("other:abc") is None
    assert parse_callback("details:") is None


# --- обработчики ----------------------------------------------------------


async def test_details_returns_stored_confirmation(database: Database, clock: FakeClock) -> None:
    """``/details K1234`` отвечает по сохранённому результату."""
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text(f"/details {harness.result.k_id}")

    assert response.handled
    assert str(harness.result.k_id) in response.text
    assert "Подтверждено: 1" in response.text


async def test_details_reports_unknown_k_id(database: Database, clock: FakeClock) -> None:
    """Неизвестный K-ID не приводит к ошибке подсистемы."""
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text("/details K9999")

    assert response.handled is False
    assert "не найден" in response.text


async def test_details_rejects_malformed_id(database: Database, clock: FakeClock) -> None:
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text("/details not-an-id")

    assert response.handled is False
    assert "некорректный" in response.text


async def test_level2_lists_active_jobs(database: Database, clock: FakeClock) -> None:
    """``/level2`` показывает активные Job'ы."""
    harness = await build_notifications(database, clock)
    jobs = SqliteJobRepository(database)
    await jobs.update_status(harness.result.k_id, JobStatus.QUEUED, updated_at=clock.now())
    router = await build_router(harness, database)

    response = await router.handle_text("/level2")

    assert str(harness.result.k_id) in response.text


async def test_level2_reports_empty_queue(database: Database, clock: FakeClock) -> None:
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text("/level2")

    assert "активных Level 2 задач нет" in response.text


async def test_status_lists_components(database: Database, clock: FakeClock) -> None:
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text("/status")

    assert "level1: running" in response.text
    assert "level2: running (0 active)" in response.text


async def test_stats_includes_confirmation_rate(database: Database, clock: FakeClock) -> None:
    """``/stats`` показывает confirmation rate по формуле ``CLAUDE.md`` §27."""
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    response = await router.handle_text("/stats")

    # 3 / (3 + 1) x 100 = 75.00 %, PARTIAL исключён.
    assert "Confirmation rate: 75.00%" in response.text
    assert "Неопределённых сумм: 2" in response.text


async def test_stats_reports_not_available(database: Database, clock: FakeClock) -> None:
    """Без решений confirmation rate — ``N/A``."""
    harness = await build_notifications(database, clock)
    router = await build_router(
        harness,
        database,
        stats=StaticStats(StatsSnapshot(confirmations=ConfirmationStatistics(partial=4))),
    )

    response = await router.handle_text("/stats")

    assert "Confirmation rate: N/A" in response.text


async def test_details_button_uses_stored_text(database: Database, clock: FakeClock) -> None:
    """Нажатие кнопки ``об`` читает подготовленный текст (``CLAUDE.md`` §35)."""
    harness = await build_notifications(database, clock)
    stored = await harness.notifications.list_for_opportunity(harness.opportunity.opportunity_id)
    router = await build_router(harness, database)

    response = await router.handle_callback(f"details:{stored[0].notification_id}")

    _, details = await harness.notifications.load_texts(stored[0].notification_id)
    assert response.text == details


async def test_unknown_callback_is_handled(database: Database, clock: FakeClock) -> None:
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)

    assert (await router.handle_callback("details:missing")).handled is False
    assert (await router.handle_callback("garbage")).handled is False


async def test_handlers_never_call_provider_api(database: Database, clock: FakeClock) -> None:
    """Команды не инициируют запрос к провайдеру котировок."""
    harness = await build_notifications(database, clock)
    router = await build_router(harness, database)
    stored = await harness.notifications.list_for_opportunity(harness.opportunity.opportunity_id)
    before = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())

    for text in ("/level2", "/status", "/stats", f"/details {harness.result.k_id}"):
        await router.handle_text(text)
    await router.handle_callback(f"details:{stored[0].notification_id}")

    after = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    assert before > 0, "фикстуре нужны выполненные Level 1/Level 2 запросы"
    assert after == before


# --- входящий канал -------------------------------------------------------


def build_service(
    router: CommandRouter,
    updates: FakeUpdates,
    database: Database,
    clock: FakeClock,
    *,
    transport: FakeTransport | None = None,
    allowed: frozenset[str] = frozenset(),
) -> CommandService:
    return CommandService(
        router=router,
        updates=updates,
        transport=transport or FakeTransport(),
        destination=DESTINATION,
        offsets=SqliteMetadataRepository(database),
        clock=clock,
        allowed_chat_ids=allowed,
    )


async def test_offset_is_persisted(database: Database, clock: FakeClock) -> None:
    """Offset переживает рестарт."""
    harness = await build_notifications(database, clock)
    updates = FakeUpdates(batches=[(TelegramUpdate(update_id=10, chat_id="1", text="/status"),)])
    service = build_service(await build_router(harness, database), updates, database, clock)

    await service.poll_once()

    stored = await SqliteMetadataRepository(database).get(OFFSET_KEY)
    assert stored == "11"
    assert updates.offsets == [None]


async def test_duplicate_update_is_ignored(database: Database, clock: FakeClock) -> None:
    """Повторно доставленное обновление обрабатывается один раз."""
    harness = await build_notifications(database, clock)
    update = TelegramUpdate(update_id=5, chat_id="1", text="/status")
    updates = FakeUpdates(batches=[(update,), (update,)])
    transport = FakeTransport()
    service = build_service(
        await build_router(harness, database), updates, database, clock, transport=transport
    )

    await service.poll_once()
    await service.poll_once()

    assert len(transport.sent) == 1


async def test_command_from_unknown_chat_is_ignored(database: Database, clock: FakeClock) -> None:
    """Источник команды проверяется по конфигурации."""
    harness = await build_notifications(database, clock)
    updates = FakeUpdates(batches=[(TelegramUpdate(update_id=1, chat_id="999", text="/status"),)])
    transport = FakeTransport()
    service = build_service(
        await build_router(harness, database),
        updates,
        database,
        clock,
        transport=transport,
        allowed=frozenset({"1"}),
    )

    responses = await service.poll_once()

    assert responses == ()
    assert transport.sent == []


async def test_callback_is_acknowledged(database: Database, clock: FakeClock) -> None:
    """Нажатие кнопки подтверждается Telegram."""
    harness = await build_notifications(database, clock)
    stored = await harness.notifications.list_for_opportunity(harness.opportunity.opportunity_id)
    updates = FakeUpdates(
        batches=[
            (
                TelegramUpdate(
                    update_id=2,
                    chat_id="1",
                    callback_data=f"details:{stored[0].notification_id}",
                    callback_query_id="cb-1",
                ),
            )
        ]
    )
    service = build_service(await build_router(harness, database), updates, database, clock)

    responses = await service.poll_once()

    assert updates.answered == ["cb-1"]
    assert responses and responses[0].handled


async def test_commands_do_not_block_the_scanner(database: Database, clock: FakeClock) -> None:
    """Медленная обработка команды не задерживает сканирование (``CLAUDE.md`` §35)."""
    harness = await build_notifications(database, clock)
    gate = asyncio.Event()

    class SlowUpdates(FakeUpdates):
        async def fetch(self, *, offset: int | None, limit: int = 20) -> tuple[TelegramUpdate, ...]:
            await gate.wait()
            return ()

    service = build_service(await build_router(harness, database), SlowUpdates(), database, clock)
    polling = asyncio.ensure_future(service.poll_once())
    await asyncio.sleep(0)

    scan_marker = Decimal(0)
    for _ in range(3):
        # Работа сканера продолжается, пока команда ждёт обновлений.
        scan_marker += Decimal(1)
        await asyncio.sleep(0)

    assert scan_marker == Decimal(3)
    assert not polling.done()
    gate.set()
    await polling
