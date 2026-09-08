"""Telegram: изолированный адаптер доставки уведомлений.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).
"""

from monik.infrastructure.telegram.adapter import (
    TELEGRAM_NETWORK,
    TELEGRAM_RESOURCE_OWNER,
    TelegramNotificationAdapter,
)
from monik.infrastructure.telegram.endpoints import (
    ANSWER_CALLBACK_PATH,
    DEFAULT_BASE_URL,
    GET_UPDATES_PATH,
    SEND_MESSAGE_PATH,
    bot_path,
)
from monik.infrastructure.telegram.fake import FakeTransport

__all__ = [
    "ANSWER_CALLBACK_PATH",
    "DEFAULT_BASE_URL",
    "GET_UPDATES_PATH",
    "SEND_MESSAGE_PATH",
    "TELEGRAM_NETWORK",
    "TELEGRAM_RESOURCE_OWNER",
    "FakeTransport",
    "TelegramNotificationAdapter",
    "bot_path",
]
