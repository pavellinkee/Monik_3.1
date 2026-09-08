"""Telegram Notification Adapter.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

Все запросы выполняются через Resource Manager
(``15_NOTIFICATION_SYSTEM.md`` §29): собственных повторов, очередей и
ограничений частоты адаптер не создаёт — это ответственность Resource
Manager и Notification System.

Токен бота не попадает ни в логи, ни в исключения (§70).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from monik.config.secrets import SecretValue
from monik.config.sections.notifications import TelegramConfig
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.notifications import DeliveryErrorKind
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    MonikError,
    NetworkError,
    ProviderError,
    RateLimitError,
)
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.http import HttpClient, HttpRequest, HttpResponse, classify_response
from monik.infrastructure.telegram.endpoints import SEND_MESSAGE_PATH, bot_path
from monik.services.notifications.ports import DeliveryReceipt, OutgoingMessage
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["TELEGRAM_NETWORK", "TELEGRAM_RESOURCE_OWNER", "TelegramNotificationAdapter"]

#: Владелец ресурса Telegram в Resource Manager: это не агрегатор, поэтому
#: идентификатор строковый (``01_PROJECT_REQUIREMENTS.md`` §34).
TELEGRAM_RESOURCE_OWNER = "telegram"

#: Telegram не относится к блокчейн-сети; ключ ресурса требует значения.
TELEGRAM_NETWORK = NetworkId("telegram")


class TelegramNotificationAdapter:
    """Отправляет сообщения через Telegram Bot API."""

    def __init__(
        self,
        config: TelegramConfig,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        bot_token: SecretValue,
        chat_id: SecretValue,
    ) -> None:
        self._config = config
        self._http = http
        self._resources = resources
        self._clock = clock
        self._bot_token = bot_token
        self._chat_id = chat_id

    async def send(self, message: OutgoingMessage) -> DeliveryReceipt:
        """Отправить сообщение и вернуть нормализованный результат.

        Ошибка классифицируется (``15_NOTIFICATION_SYSTEM.md`` §64), а не
        превращается в «успешную» доставку (§78).
        """
        payload: dict[str, Any] = {
            "chat_id": self._chat_id.get(),
            "text": message.text,
            "disable_web_page_preview": True,
        }
        markup = self._reply_markup(message)
        if markup is not None:
            payload["reply_markup"] = markup

        try:
            response = await self._request(payload, message)
        except MonikError as error:
            return _receipt_from_error(error)

        return self._receipt_from_response(response)

    async def aclose(self) -> None:
        """Освободить ресурсы HTTP-клиента."""
        await self._http.aclose()

    # --- внутреннее -------------------------------------------------------

    @staticmethod
    def _reply_markup(message: OutgoingMessage) -> dict[str, Any] | None:
        """Inline-кнопка ``об`` (``CLAUDE.md`` §35).

        Кнопка несёт только ссылку на сохранённое уведомление: обработка
        нажатия не выполняет нового API-запроса.
        """
        if message.details_callback is None or message.details_label is None:
            return None
        return {
            "inline_keyboard": [
                [{"text": message.details_label, "callback_data": message.details_callback}]
            ]
        }

    async def _request(self, payload: dict[str, Any], message: OutgoingMessage) -> HttpResponse:
        request = ResourceRequest(
            request_id=RequestId.generate(),
            key=ResourceKey(
                provider_id=TELEGRAM_RESOURCE_OWNER,
                network_id=TELEGRAM_NETWORK,
                operation=CapabilityOperation.TOKEN_METADATA,
            ),
            priority=RequestPriority.BACKGROUND,
            timeout=timedelta(seconds=self._config.request_timeout_seconds),
            created_at=self._clock.now(),
            sequence=0,
            deduplication_key=f"telegram:{message.destination.destination_id}",
        )

        async def call() -> HttpResponse:
            response = await self._http.send(
                HttpRequest(
                    method="POST",
                    url=f"{self._config.api_base_url.rstrip('/')}"
                    f"{bot_path(self._bot_token.get(), SEND_MESSAGE_PATH)}",
                    json_body=payload,
                    request_id=request.request_id,
                    timeout_seconds=self._config.request_timeout_seconds,
                )
            )
            classify_response(response, provider=TELEGRAM_RESOURCE_OWNER)
            return response

        return await self._resources.execute(request, call)

    @staticmethod
    def _receipt_from_response(response: HttpResponse) -> DeliveryReceipt:
        """Разобрать ответ Bot API.

        ``ok: false`` не считается доставкой: подтверждение обязано быть
        явным (``15_NOTIFICATION_SYSTEM.md`` §62, §78).
        """
        body = response.json()
        if not isinstance(body, dict) or not body.get("ok"):
            description = ""
            if isinstance(body, dict):
                description = str(body.get("description", ""))
            return DeliveryReceipt(
                delivered=False,
                error_kind=DeliveryErrorKind.PROVIDER_ERROR,
                error_message=description or "telegram rejected the message",
            )
        result = body.get("result")
        message_id = None
        if isinstance(result, dict) and result.get("message_id") is not None:
            message_id = str(result["message_id"])
        return DeliveryReceipt(delivered=True, external_message_id=message_id)


def _receipt_from_error(error: MonikError) -> DeliveryReceipt:
    """Классифицировать нормализованную ошибку (§64-67)."""
    if isinstance(error, RateLimitError):
        retry_after = error.info.retry_after
        return DeliveryReceipt(
            delivered=False,
            error_kind=DeliveryErrorKind.RATE_LIMIT,
            error_message=error.info.message,
            retry_after_seconds=retry_after.total_seconds() if retry_after else None,
        )
    if isinstance(error, AuthenticationError):
        return DeliveryReceipt(
            delivered=False,
            error_kind=DeliveryErrorKind.AUTH_ERROR,
            error_message=error.info.message,
        )
    if isinstance(error, DataError):
        return DeliveryReceipt(
            delivered=False,
            error_kind=DeliveryErrorKind.INVALID_REQUEST,
            error_message=error.info.message,
        )
    if isinstance(error, NetworkError):
        return DeliveryReceipt(
            delivered=False,
            error_kind=DeliveryErrorKind.NETWORK_ERROR,
            error_message=error.info.message,
        )
    if isinstance(error, ProviderError):
        return DeliveryReceipt(
            delivered=False,
            error_kind=DeliveryErrorKind.PROVIDER_ERROR,
            error_message=error.info.message,
        )
    return DeliveryReceipt(
        delivered=False,
        error_kind=DeliveryErrorKind.UNKNOWN_ERROR,
        error_message=error.info.message,
    )
