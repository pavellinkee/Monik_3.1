"""Объединение одинаковых одновременных запросов.

Если несколько потребителей одновременно запрашивают одно и то же, запрос
выполняется один раз, а результат получают все
(``12_RESOURCE_MANAGER.md`` §45, ``01_PROJECT_REQUIREMENTS.md`` §41).

Дедупликация **не меняет семантику** запроса
(``12_RESOURCE_MANAGER.md`` §46): объединяются только запросы с одинаковым
ключом, который формирует вызывающая сторона.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

__all__ = ["InFlightRegistry"]


class InFlightRegistry:
    """Реестр выполняющихся запросов по ключу дедупликации."""

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Task[Any]] = {}
        self.merged_count = 0

    @property
    def in_flight(self) -> int:
        """Сколько запросов выполняется сейчас."""
        return len(self._in_flight)

    def is_in_flight(self, key: str) -> bool:
        """Выполняется ли уже запрос с этим ключом."""
        return key in self._in_flight

    async def run[T](self, key: str, operation: Callable[[], Awaitable[T]]) -> T:
        """Выполнить операцию, объединив её с уже выполняющейся такой же.

        Присоединившийся потребитель получает тот же результат или ту же
        ошибку, что и первый: отдельного запроса к провайдеру не делается.
        """
        existing = self._in_flight.get(key)
        if existing is not None:
            self.merged_count += 1
            result: T = await asyncio.shield(existing)
            return result

        task: asyncio.Task[T] = asyncio.ensure_future(operation())
        self._in_flight[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if self._in_flight.get(key) is task:
                del self._in_flight[key]
