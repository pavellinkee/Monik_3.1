"""Разбор входящих команд Telegram.

Поддерживаются команды ``CLAUDE.md`` §36:

``/details K1234`` · ``/level2`` · ``/status`` · ``/stats``

Некорректный ввод не приводит к ошибке подсистемы: он превращается в
явный результат разбора, который обработчик показывает пользователю.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ["CommandName", "ParsedCommand", "parse_callback", "parse_command"]

#: Префикс callback-данных кнопки ``об``.
DETAILS_CALLBACK_PREFIX = "details"


class CommandName(StrEnum):
    """Поддерживаемая команда."""

    DETAILS = "details"
    LEVEL2 = "level2"
    STATUS = "status"
    STATS = "stats"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    """Результат разбора текста команды."""

    name: CommandName
    argument: str | None = None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        """Распознана ли команда полностью."""
        return self.name is not CommandName.UNKNOWN and self.error is None


def parse_command(text: str) -> ParsedCommand:
    """Разобрать текст сообщения.

    Бот может получать команду с суффиксом ``@botname``: он отбрасывается,
    потому что не является частью имени команды.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ParsedCommand(name=CommandName.UNKNOWN, error="not a command")
    parts = stripped.split()
    raw_name = parts[0][1:].split("@", maxsplit=1)[0].lower()
    argument = parts[1] if len(parts) > 1 else None

    if raw_name == CommandName.DETAILS.value:
        if argument is None:
            return ParsedCommand(
                name=CommandName.DETAILS, error="команда /details требует идентификатор K"
            )
        return ParsedCommand(name=CommandName.DETAILS, argument=argument)
    if raw_name in {CommandName.LEVEL2.value, CommandName.STATUS.value, CommandName.STATS.value}:
        return ParsedCommand(name=CommandName(raw_name))
    return ParsedCommand(name=CommandName.UNKNOWN, error=f"неизвестная команда /{raw_name}")


def parse_callback(data: str) -> str | None:
    """Идентификатор уведомления из callback-данных кнопки ``об``."""
    prefix = f"{DETAILS_CALLBACK_PREFIX}:"
    if not data.startswith(prefix):
        return None
    notification_id = data[len(prefix) :].strip()
    return notification_id or None
