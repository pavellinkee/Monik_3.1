"""Очередь доступа к ресурсу с учётом приоритета.

Порядок обслуживания определяется приоритетом, затем временем постановки и
sequence (``04_SCHEDULER.md`` §25, ``05_RESOURCE_MANAGER.md`` §17).
Прибыльность возможности на порядок не влияет
(``04_SCHEDULER.md`` §26).

При переполнении очереди применяется backpressure: запрос отклоняется явной
ошибкой, а не копится бесконечно (``12_RESOURCE_MANAGER.md`` §42-43).
"""

from __future__ import annotations

import asyncio
import builtins
import heapq
from dataclasses import dataclass, field

from monik.domain.errors import ResourceError, TimeoutError
from monik.domain.models.resource import ResourceRequest

__all__ = ["PriorityGate"]


@dataclass(order=True)
class _Waiter:
    """Ожидающий запрос в очереди."""

    ordering_key: tuple[int, object, int]
    tiebreaker: int
    future: asyncio.Future[None] = field(compare=False)


class PriorityGate:
    """Пропускает ограниченное число одновременных операций."""

    def __init__(self, *, limit: int, capacity: int, name: str) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._limit = limit
        self._capacity = capacity
        self._name = name
        self._active = 0
        self._waiters: list[_Waiter] = []
        self._sequence = 0

    @property
    def active(self) -> int:
        """Число выполняющихся операций."""
        return self._active

    @property
    def waiting(self) -> int:
        """Число ожидающих операций."""
        return len(self._waiters)

    async def acquire(self, request: ResourceRequest, *, timeout: float) -> None:
        """Дождаться разрешения на выполнение.

        Ожидание ограничено таймаутом: запрос не может ждать бесконечно.
        """
        if self._active < self._limit and not self._waiters:
            self._active += 1
            return
        if len(self._waiters) >= self._capacity:
            raise ResourceError(
                f"queue for {self._name} is full ({self._capacity} waiting)",
                code="resource_queue_overflow",
                request_id=request.request_id,
            )
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        self._sequence += 1
        waiter = _Waiter(
            ordering_key=(
                request.priority.rank,
                request.created_at,
                request.sequence,
            ),
            tiebreaker=self._sequence,
            future=future,
        )
        heapq.heappush(self._waiters, waiter)
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except TimeoutError:
            raise
        except builtins.TimeoutError as exc:
            self._discard(waiter)
            raise TimeoutError(
                f"waiting for {self._name} exceeded {timeout} seconds",
                code="resource_wait_timeout",
                request_id=request.request_id,
            ) from exc
        except asyncio.CancelledError:
            self._discard(waiter)
            raise

    def release(self) -> None:
        """Освободить слот и пропустить следующий по приоритету запрос.

        Слот освобождается всегда, в том числе при исключении: утечка
        разрешения недопустима (``12_RESOURCE_MANAGER.md`` §41).
        """
        while self._waiters:
            waiter = heapq.heappop(self._waiters)
            if not waiter.future.done():
                waiter.future.set_result(None)
                return
        self._active = max(0, self._active - 1)

    def _discard(self, waiter: _Waiter) -> None:
        """Убрать ожидающего, который больше не ждёт."""
        if waiter.future.done() and not waiter.future.cancelled():
            # Разрешение успели выдать: слот возвращается следующему в очереди,
            # иначе он был бы потерян навсегда.
            self.release()
            return
        try:
            self._waiters.remove(waiter)
        except ValueError:
            return
        heapq.heapify(self._waiters)
