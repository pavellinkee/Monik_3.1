"""Входящий канал Telegram: long polling ``getUpdates``.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

Запросы выполняются через Resource Manager с фоновым приоритетом
(``15_NOTIFICATION_SYSTEM.md`` §29): входящий канал не конкурирует со
сканером за ресурсы и не блокирует его (``CLAUDE.md`` §35).

Offset переживает рестарт, а повторно доставленные ``update_id``
отбрасываются: Telegram гарантирует at-least-once доставку.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from monik.config.secrets import SecretValue
from monik.config.sections.notifications import TelegramConfig
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import DataError
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.domain.value_objects.identifiers import RequestId
from monik.infrastructure.http import HttpClient, HttpRequest, HttpResponse, classify_response
from monik.infrastructure.telegram.adapter import TELEGRAM_NETWORK, TELEGRAM_RESOURCE_OWNER
from monik.infrastructure.telegram.endpoints import (
    ANSWER_CALLBACK_PATH,
    GET_UPDATES_PATH,
    bot_path,
)
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["TelegramUpdate", "TelegramUpdateSource"]


@dataclass(frozen=True, slots=True)
class TelegramUpdate:
    """Нормализованное входящее обновление.

    Наружу не выходит raw-структура Bot API: провайдер-специфика остаётся
    внутри адаптера (``15_NOTIFICATION_SYSTEM.md`` §10).
    """

    update_id: int
    chat_id: str | None = None
    text: str | None = None
    callback_data: str | None = None
    callback_query_id: str | None = None

    @property
    def is_command(self) -> bool:
        """Является ли обновление текстовой командой."""
        return bool(self.text and self.text.startswith("/"))

    @property
    def is_callback(self) -> bool:
        """Является ли обновление нажатием inline-кнопки."""
        return self.callback_data is not None


class TelegramUpdateSource:
    """Получает обновления Bot API."""

    def __init__(
        self,
        config: TelegramConfig,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        bot_token: SecretValue,
    ) -> None:
        self._config = config
        self._http = http
        self._resources = resources
        self._clock = clock
        self._bot_token = bot_token

    async def fetch(self, *, offset: int | None, limit: int = 20) -> tuple[TelegramUpdate, ...]:
        """Получить порцию обновлений начиная с ``offset``."""
        payload: dict[str, Any] = {"limit": limit, "timeout": 0}
        if offset is not None:
            payload["offset"] = offset
        response = await self._request(GET_UPDATES_PATH, payload, operation="get_updates")
        return _parse_updates(response)

    async def answer_callback(self, callback_query_id: str, *, text: str | None = None) -> None:
        """Подтвердить обработку нажатия кнопки."""
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text[:200]
        await self._request(ANSWER_CALLBACK_PATH, payload, operation="answer_callback")

    async def aclose(self) -> None:
        """Освободить ресурсы HTTP-клиента."""
        await self._http.aclose()

    async def _request(
        self, method: str, payload: dict[str, Any], *, operation: str
    ) -> HttpResponse:
        request = ResourceRequest(
            request_id=RequestId.generate(),
            key=ResourceKey(
                provider_id=TELEGRAM_RESOURCE_OWNER,
                network_id=TELEGRAM_NETWORK,
                operation=CapabilityOperation.TOKEN_METADATA,
            ),
            # Фоновый приоритет: входящий канал не вытесняет Level 1 и
            # Level 2 (``CLAUDE.md`` §15, §35).
            priority=RequestPriority.BACKGROUND,
            timeout=timedelta(seconds=self._config.request_timeout_seconds),
            created_at=self._clock.now(),
            sequence=0,
            deduplication_key=f"telegram:{operation}",
        )

        async def call() -> HttpResponse:
            response = await self._http.send(
                HttpRequest(
                    method="POST",
                    url=f"{self._config.api_base_url.rstrip('/')}"
                    f"{bot_path(self._bot_token.get(), method)}",
                    json_body=payload,
                    request_id=request.request_id,
                    timeout_seconds=self._config.request_timeout_seconds,
                )
            )
            classify_response(response, provider=TELEGRAM_RESOURCE_OWNER)
            return response

        return await self._resources.execute(request, call)


def _parse_updates(response: HttpResponse) -> tuple[TelegramUpdate, ...]:
    """Разобрать ответ ``getUpdates``.

    Некорректная структура — ошибка данных, а не пустой список: молча
    терять обновления нельзя (``18_ERROR_HANDLING.md``).
    """
    body = response.json()
    if not isinstance(body, dict) or not body.get("ok"):
        raise DataError(
            "telegram getUpdates returned an unsuccessful response",
            provider_code=TELEGRAM_RESOURCE_OWNER,
        )
    result = body.get("result")
    if not isinstance(result, list):
        raise DataError(
            "telegram getUpdates result is not a list", provider_code=TELEGRAM_RESOURCE_OWNER
        )
    return tuple(_parse_update(item) for item in result if isinstance(item, dict))


def _parse_update(item: dict[str, Any]) -> TelegramUpdate:
    """Разобрать одно обновление."""
    update_id = item.get("update_id")
    if not isinstance(update_id, int):
        raise DataError(
            "telegram update has no numeric update_id", provider_code=TELEGRAM_RESOURCE_OWNER
        )
    message = item.get("message")
    if isinstance(message, dict):
        chat = message.get("chat")
        chat_id = str(chat["id"]) if isinstance(chat, dict) and "id" in chat else None
        text = message.get("text")
        return TelegramUpdate(
            update_id=update_id,
            chat_id=chat_id,
            text=str(text) if isinstance(text, str) else None,
        )
    callback = item.get("callback_query")
    if isinstance(callback, dict):
        callback_message = callback.get("message")
        chat_id = None
        if isinstance(callback_message, dict):
            chat = callback_message.get("chat")
            if isinstance(chat, dict) and "id" in chat:
                chat_id = str(chat["id"])
        data = callback.get("data")
        return TelegramUpdate(
            update_id=update_id,
            chat_id=chat_id,
            callback_data=str(data) if isinstance(data, str) else None,
            callback_query_id=str(callback.get("id")) if callback.get("id") else None,
        )
    return TelegramUpdate(update_id=update_id)
