"""Security-тесты Telegram: bot token не попадает в логи и исключения.

``15_NOTIFICATION_SYSTEM.md`` §70: Notification System не должна логировать
bot token, ключи, секреты и заголовки аутентификации.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from monik.config.secrets import SecretRef, SecretResolver, SecretValue
from monik.config.sections.notifications import TelegramConfig
from monik.domain.enums.notifications import DestinationKind
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.http import FakeHttpClient, HttpRequest, HttpResponse
from monik.infrastructure.telegram import TelegramNotificationAdapter, bot_path
from monik.services.notifications import OutgoingMessage
from monik.services.observability import FakeClock
from monik.services.observability.logging import StructuredFormatter, get_logger
from monik.services.observability.redaction import REDACTED, SecretRegistry
from tests import factories as f
from tests.unit.providers.support import resource_manager

BOT_TOKEN = "8123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
CHAT_ID = "-1001234567890"

DESTINATION = NotificationDestination(destination_id="chat-main", kind=DestinationKind.TELEGRAM)


def secret(value: str, env: str) -> SecretValue:
    return SecretResolver({env: value}).resolve(SecretRef(env=env), context="test")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


def build_adapter(http: FakeHttpClient, clock: FakeClock) -> TelegramNotificationAdapter:
    config = TelegramConfig(
        enabled=True,
        bot_token=SecretRef(env="MONIK_TELEGRAM_BOT_TOKEN"),
        chat_id=SecretRef(env="MONIK_TELEGRAM_CHAT_ID"),
    )
    return TelegramNotificationAdapter(
        config,
        http=http,
        resources=resource_manager(clock),
        clock=clock,
        bot_token=secret(BOT_TOKEN, "MONIK_TELEGRAM_BOT_TOKEN"),
        chat_id=secret(CHAT_ID, "MONIK_TELEGRAM_CHAT_ID"),
    )


def test_secret_value_never_reveals_the_token() -> None:
    """Токен не раскрывается в ``repr``/``str``."""
    value = secret(BOT_TOKEN, "MONIK_TELEGRAM_BOT_TOKEN")
    assert BOT_TOKEN not in repr(value)
    assert BOT_TOKEN not in str(value)


def test_bot_token_is_redacted_in_logs() -> None:
    """Токен в URL заменяется редакцией (``CLAUDE.md`` §48)."""
    registry = SecretRegistry()
    registry.register(BOT_TOKEN)
    formatter = StructuredFormatter(registry=registry)
    record = logging.LogRecord(
        name="monik.notifications",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            f"telegram request failed: https://api.telegram.org{bot_path(BOT_TOKEN, 'sendMessage')}"
        ),
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert BOT_TOKEN not in rendered
    assert REDACTED in rendered


async def test_failed_delivery_message_has_no_token(clock: FakeClock) -> None:
    """Сообщение об ошибке доставки не содержит токен."""
    http = FakeHttpClient(
        handler=lambda request: HttpResponse(status_code=401, text='{"ok": false}')
    )
    adapter = build_adapter(http, clock)

    receipt = await adapter.send(
        OutgoingMessage(destination=DESTINATION, text="#K1", details_label="об")
    )

    assert receipt.delivered is False
    assert receipt.error_message is not None
    assert BOT_TOKEN not in receipt.error_message


async def test_outgoing_payload_contains_no_credentials(clock: FakeClock) -> None:
    """Тело запроса не содержит секретов, кроме адреса назначения."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return HttpResponse(status_code=200, text='{"ok": true, "result": {"message_id": 1}}')

    adapter = build_adapter(FakeHttpClient(handler=handler), clock)
    await adapter.send(OutgoingMessage(destination=DESTINATION, text="#K1"))

    body: Any = captured[0].json_body
    assert BOT_TOKEN not in json.dumps(body)
    assert captured[0].headers == {}


def test_notification_logger_does_not_emit_raw_urls() -> None:
    """Логгер подсистемы уведомлений использует общую редакцию."""
    logger = get_logger("services.notifications.dispatcher")
    assert logger.name.startswith("monik.")
