"""Endpoints Telegram Bot API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3):
``api.telegram.org`` недоступен из среды разработки, поэтому контракт
описан по официальной документации Bot API и проверяется скриптом
``scripts/verify_provider_api.py`` в среде с сетевым доступом и токеном.

Все provider-specific детали Telegram собраны здесь: остальной код
работает с нормализованными моделями (``15_NOTIFICATION_SYSTEM.md`` §10).
"""

from __future__ import annotations

__all__ = [
    "ANSWER_CALLBACK_PATH",
    "DEFAULT_BASE_URL",
    "GET_UPDATES_PATH",
    "SEND_MESSAGE_PATH",
    "bot_path",
]

#: Базовый URL Bot API. Переопределяется конфигурацией.
DEFAULT_BASE_URL = "https://api.telegram.org"

#: Отправка сообщения.
SEND_MESSAGE_PATH = "sendMessage"

#: Получение обновлений (входящий канал, этап S16).
GET_UPDATES_PATH = "getUpdates"

#: Ответ на нажатие inline-кнопки.
ANSWER_CALLBACK_PATH = "answerCallbackQuery"


def bot_path(token: str, method: str) -> str:
    """Путь метода Bot API для конкретного бота.

    Токен является частью пути, поэтому URL никогда не логируется целиком:
    редакция логов удаляет его (``22_SECURITY.md``, ``CLAUDE.md`` §48).
    """
    return f"/bot{token}/{method}"
