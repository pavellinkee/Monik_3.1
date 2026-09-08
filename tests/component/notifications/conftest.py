"""Окружение тестов Notification System."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from monik.config import Configuration, parse_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.notifications import DestinationKind, NotificationMode
from monik.domain.enums.providers import ProviderId
from monik.domain.models.confirmation import ConfirmationSnapshot
from monik.domain.models.job import ConfirmationResult
from monik.domain.models.notification import NotificationDestination
from monik.domain.models.opportunity import Opportunity
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.providers.fake import FakeAdapter
from monik.infrastructure.telegram import FakeTransport
from monik.repositories.sqlite import (
    SqliteConfirmationRepository,
    SqliteIdSequenceRepository,
    SqliteNotificationRepository,
    SqliteOpportunityRepository,
)
from monik.services.notifications import MessageFormatter, NotificationDispatcher
from monik.services.observability import FakeClock
from monik.services.opportunity import OpportunityService, build_snapshot
from monik.services.registries import TokenRegistry
from tests import factories as f
from tests.component.level1.conftest import level1_document
from tests.component.level2.conftest import build_level2
from tests.unit.config.conftest import VALID_ENV

TELEGRAM = NotificationDestination(
    destination_id="chat-main", kind=DestinationKind.TELEGRAM, mode=NotificationMode.A
)
SECOND = NotificationDestination(
    destination_id="chat-backup", kind=DestinationKind.TELEGRAM, mode=NotificationMode.B
)


def notification_document(**notification_overrides: object) -> dict[str, object]:
    """Конфигурация с включённой доставкой в Telegram."""
    document = level1_document()
    telegram = {
        "enabled": True,
        "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
        "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
    }
    notifications: dict[str, object] = {"enabled": True, "telegram": telegram}
    notifications.update(notification_overrides)
    document["notifications"] = notifications
    return document


def notification_env() -> dict[str, str]:
    """Окружение с тестовыми credentials Telegram."""
    return {
        **VALID_ENV,
        "MONIK_TELEGRAM_BOT_TOKEN": "8123456789:test-bot-token-value-0000",
        "MONIK_TELEGRAM_CHAT_ID": "-1001234567890",
    }


def configured(**notification_overrides: object) -> Configuration:
    return parse_configuration(
        notification_document(**notification_overrides), environ=notification_env()
    ).config


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "notify.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@dataclass
class NotificationHarness:
    """Подтверждённая возможность вместе с очередью доставки."""

    configuration: Configuration
    opportunity: Opportunity
    result: ConfirmationResult
    snapshot: ConfirmationSnapshot
    service: OpportunityService
    dispatcher: NotificationDispatcher
    transport: FakeTransport
    notifications: SqliteNotificationRepository
    opportunities: SqliteOpportunityRepository
    formatter: MessageFormatter
    clock: FakeClock
    adapters: dict[ProviderId, FakeAdapter]


async def build_notifications(
    database: Database,
    clock: FakeClock,
    *,
    configuration: Configuration | None = None,
    transport: FakeTransport | None = None,
    destinations: tuple[NotificationDestination, ...] = (TELEGRAM,),
    queue: bool = True,
) -> NotificationHarness:
    """Подтвердить возможность и собрать над ней Notification System."""
    config = configuration or configured()
    level2 = await build_level2(config, database, clock)
    result = await level2.scanner.confirm(level2.job)
    tokens = TokenRegistry(config)
    formatter = MessageFormatter(config.notifications, tokens)
    service = OpportunityService(
        publisher=SqliteConfirmationRepository(database),
        notifications=SqliteNotificationRepository(database),
        opportunities=SqliteOpportunityRepository(database),
        sequences=SqliteIdSequenceRepository(database),
        clock=clock,
        destinations=destinations,
        renderer=formatter,
    )
    if queue:
        await service.record_confirmation(level2.opportunity, result)
    delivery_transport = transport or FakeTransport()
    dispatcher = NotificationDispatcher(
        config.notifications,
        store=SqliteNotificationRepository(database),
        transports={DestinationKind.TELEGRAM.value: delivery_transport},
        clock=clock,
    )
    return NotificationHarness(
        configuration=config,
        opportunity=level2.opportunity,
        result=result,
        snapshot=build_snapshot(level2.opportunity, result),
        service=service,
        dispatcher=dispatcher,
        transport=delivery_transport,
        notifications=SqliteNotificationRepository(database),
        opportunities=SqliteOpportunityRepository(database),
        formatter=formatter,
        clock=clock,
        adapters=level2.adapters,
    )
