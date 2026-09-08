"""Абстракция времени.

Логика, зависящая от времени (freshness, expiration, scheduler, retry,
retention), обязана использовать инъектируемый Clock
(``38_INTERFACES.md`` §39-41, ``25_PROJECT_STRUCTURE.md`` §60). Прямое
обращение к системным часам делает тесты недетерминированными.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

__all__ = ["Clock", "FakeClock", "SystemClock"]


@runtime_checkable
class Clock(Protocol):
    """Источник текущего времени."""

    def now(self) -> datetime:
        """Текущее время в UTC (timezone-aware)."""
        ...

    def monotonic(self) -> float:
        """Монотонные секунды для измерения длительности.

        Не подвержено переводу системных часов, поэтому пригодно для
        таймаутов и измерения latency.
        """
        ...


class SystemClock:
    """Реальные системные часы."""

    def now(self) -> datetime:
        """Текущее время в UTC."""
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """Монотонные секунды процесса."""
        return time.monotonic()


class FakeClock:
    """Управляемые часы для детерминированных тестов.

    Время не движется само: тест продвигает его явно через
    :meth:`advance` или :meth:`set_to`.
    """

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("FakeClock requires a timezone-aware start time")
        self._now = start.astimezone(UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        """Текущее установленное время."""
        return self._now

    def monotonic(self) -> float:
        """Накопленные монотонные секунды."""
        return self._monotonic

    def advance(self, delta: timedelta) -> datetime:
        """Продвинуть время вперёд."""
        if delta < timedelta(0):
            raise ValueError("FakeClock cannot move backwards")
        self._now += delta
        self._monotonic += delta.total_seconds()
        return self._now

    def set_to(self, moment: datetime) -> datetime:
        """Установить время явно (движение назад запрещено)."""
        if moment.tzinfo is None:
            raise ValueError("FakeClock requires a timezone-aware time")
        target = moment.astimezone(UTC)
        if target < self._now:
            raise ValueError("FakeClock cannot move backwards")
        return self.advance(target - self._now)
