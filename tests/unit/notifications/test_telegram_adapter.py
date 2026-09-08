"""Telegram Notification Adapter: запрос, кнопка и классификация ошибок.

⚠️ Контракт Bot API не проверен вживую (решение D-3): тесты используют
контролируемый HTTP-клиент.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from monik.config.secrets import SecretRef, SecretResolver, SecretValue
from monik.config.sections.notifications import TelegramConfig
from monik.domain.enums.notifications import DeliveryErrorKind, DestinationKind
from monik.domain.errors import DataError
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.http import FakeHttpClient, HttpRequest, HttpResponse
from monik.infrastructure.telegram import (
    SEND_MESSAGE_PATH,
    TelegramNotificationAdapter,
    bot_path,
)
from monik.infrastructure.telegram.polling import TelegramUpdateSource
from monik.services.notifications import OutgoingMessage
from monik.services.observability import FakeClock
from tests import factories as f
from tests.unit.providers.support import resource_manager

BOT_TOKEN = "8123456789:AAH-test-bot-token-value-000000"
CHAT_ID = "-1001234567890"

DESTINATION = NotificationDestination(destination_id="chat-main", kind=DestinationKind.TELEGRAM)


def secret(value: str, env: str) -> SecretValue:
    return SecretResolver({env: value}).resolve(SecretRef(env=env), context="test")


def message(**overrides: Any) -> OutgoingMessage:
    base: dict[str, Any] = {
        "destination": DESTINATION,
        "text": "#K1 confirmed",
        "details_callback": "details:abc",
        "details_label": "об",
    }
    base.update(overrides)
    return OutgoingMessage(**base)


def build_update_source(http: FakeHttpClient, clock: FakeClock) -> TelegramUpdateSource:
    config = TelegramConfig(
        enabled=True,
        bot_token=SecretRef(env="MONIK_TELEGRAM_BOT_TOKEN"),
        chat_id=SecretRef(env="MONIK_TELEGRAM_CHAT_ID"),
    )
    return TelegramUpdateSource(
        config,
        http=http,
        resources=resource_manager(clock),
        clock=clock,
        bot_token=secret(BOT_TOKEN, "MONIK_TELEGRAM_BOT_TOKEN"),
    )


def build_adapter(
    http: FakeHttpClient, clock: FakeClock, **config_overrides: Any
) -> TelegramNotificationAdapter:
    config = TelegramConfig(
        enabled=True,
        bot_token=SecretRef(env="MONIK_TELEGRAM_BOT_TOKEN"),
        chat_id=SecretRef(env="MONIK_TELEGRAM_CHAT_ID"),
        **config_overrides,
    )
    return TelegramNotificationAdapter(
        config,
        http=http,
        resources=resource_manager(clock),
        clock=clock,
        bot_token=secret(BOT_TOKEN, "MONIK_TELEGRAM_BOT_TOKEN"),
        chat_id=secret(CHAT_ID, "MONIK_TELEGRAM_CHAT_ID"),
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


def ok_response(message_id: int = 77) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        text=json.dumps({"ok": True, "result": {"message_id": message_id}}),
    )


async def test_successful_send_returns_message_id(clock: FakeClock) -> None:
    """Telegram message ID сохраняется (``15`` §63)."""
    http = FakeHttpClient(handler=lambda request: ok_response(4242))
    adapter = build_adapter(http, clock)

    receipt = await adapter.send(message())

    assert receipt.delivered is True
    assert receipt.external_message_id == "4242"


async def test_request_uses_the_bot_method_path(clock: FakeClock) -> None:
    """Запрос идёт на метод sendMessage конкретного бота."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return ok_response()

    adapter = build_adapter(FakeHttpClient(handler=handler), clock)
    await adapter.send(message())

    assert captured[0].method == "POST"
    assert captured[0].url.endswith(bot_path(BOT_TOKEN, SEND_MESSAGE_PATH))


async def test_message_carries_the_details_button(clock: FakeClock) -> None:
    """Каждое уведомление содержит inline-кнопку ``об`` (``CLAUDE.md`` §35)."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return ok_response()

    adapter = build_adapter(FakeHttpClient(handler=handler), clock)
    await adapter.send(message())

    markup = captured[0].json_body["reply_markup"]
    button = markup["inline_keyboard"][0][0]
    assert button["text"] == "об"
    assert button["callback_data"] == "details:abc"


async def test_chat_id_comes_from_configuration(clock: FakeClock) -> None:
    """Chat ID не зашит в код (``15`` §53)."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return ok_response()

    adapter = build_adapter(FakeHttpClient(handler=handler), clock)
    await adapter.send(message())

    assert captured[0].json_body["chat_id"] == CHAT_ID


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, DeliveryErrorKind.RATE_LIMIT),
        (401, DeliveryErrorKind.AUTH_ERROR),
        (400, DeliveryErrorKind.INVALID_REQUEST),
        (500, DeliveryErrorKind.PROVIDER_ERROR),
    ],
)
async def test_http_errors_are_classified(
    clock: FakeClock, status: int, expected: DeliveryErrorKind
) -> None:
    """Ошибки классифицируются (``15`` §64)."""
    http = FakeHttpClient(
        handler=lambda request: HttpResponse(status_code=status, text='{"ok": false}')
    )
    adapter = build_adapter(http, clock)

    receipt = await adapter.send(message())

    assert receipt.delivered is False
    assert receipt.error_kind is expected


async def test_not_ok_body_is_not_a_delivery(clock: FakeClock) -> None:
    """``ok: false`` не считается доставкой (``15`` §78)."""
    http = FakeHttpClient(
        handler=lambda request: HttpResponse(
            status_code=200, text='{"ok": false, "description": "chat not found"}'
        )
    )
    adapter = build_adapter(http, clock)

    receipt = await adapter.send(message())

    assert receipt.delivered is False
    assert receipt.error_kind is DeliveryErrorKind.PROVIDER_ERROR
    assert receipt.error_message == "chat not found"


async def test_message_without_button_is_still_sent(clock: FakeClock) -> None:
    """Транспорт не выдумывает кнопку, если её не передали."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return ok_response()

    adapter = build_adapter(FakeHttpClient(handler=handler), clock)
    await adapter.send(message(details_callback=None, details_label=None))

    assert "reply_markup" not in captured[0].json_body


# --- входящий канал -------------------------------------------------------


async def test_updates_are_normalized(clock: FakeClock) -> None:
    """``getUpdates`` превращается в нормализованные обновления."""
    payload = {
        "ok": True,
        "result": [
            {
                "update_id": 11,
                "message": {"chat": {"id": -100123}, "text": "/status"},
            },
            {
                "update_id": 12,
                "callback_query": {
                    "id": "cb-9",
                    "data": "details:abc",
                    "message": {"chat": {"id": -100123}},
                },
            },
        ],
    }
    http = FakeHttpClient(
        handler=lambda request: HttpResponse(status_code=200, text=json.dumps(payload))
    )
    source = build_update_source(http, clock)

    updates = await source.fetch(offset=None)

    assert [update.update_id for update in updates] == [11, 12]
    assert updates[0].is_command and updates[0].text == "/status"
    assert updates[1].is_callback and updates[1].callback_data == "details:abc"
    assert updates[1].callback_query_id == "cb-9"
    assert updates[0].chat_id == "-100123"


async def test_offset_is_sent_to_the_api(clock: FakeClock) -> None:
    """Offset передаётся в запрос, чтобы не получать обработанные обновления."""
    captured: list[HttpRequest] = []

    def handler(request: HttpRequest) -> HttpResponse:
        captured.append(request)
        return HttpResponse(status_code=200, text='{"ok": true, "result": []}')

    source = build_update_source(FakeHttpClient(handler=handler), clock)
    await source.fetch(offset=42)

    assert captured[0].json_body["offset"] == 42


async def test_malformed_updates_are_rejected(clock: FakeClock) -> None:
    """Некорректный ответ — ошибка данных, а не молчаливая потеря обновлений."""
    http = FakeHttpClient(
        handler=lambda request: HttpResponse(status_code=200, text='{"ok": false}')
    )
    source = build_update_source(http, clock)

    with pytest.raises(DataError):
        await source.fetch(offset=None)
