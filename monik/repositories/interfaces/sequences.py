"""Интерфейс выдачи монотонных номеров."""

from __future__ import annotations

from typing import Protocol

__all__ = ["IdSequenceRepository"]


class IdSequenceRepository(Protocol):
    """Монотонные последовательности, переживающие рестарт.

    Используется для публичных идентификаторов ``#V``/``#K``
    (``CLAUDE.md`` §20) и порядкового номера уведомлений
    (``CLAUDE.md`` §37).
    """

    async def next_value(self, name: str) -> int:
        """Выдать следующий номер последовательности."""
        ...

    async def current_value(self, name: str) -> int:
        """Текущее значение (``0``, если последовательность не использовалась)."""
        ...
