"""Очередь и воркеры Level 2.

Число одновременных подтверждений ограничено ``max_parallel``
(``CLAUDE.md`` §18, по умолчанию 20) и никогда не превышается. Количество
логических Job отделено от количества resource locks: удержание слота
очереди не означает удержание ресурса провайдера.

Одинаковые Level 2 workflow объединяются, а не выполняются дважды
(``CLAUDE.md`` §19, ``11_LEVEL_2_SCANNER.md`` §58).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from monik.config.sections.scanner import Level2Config
from monik.domain.errors import MonikError, ResourceError
from monik.domain.models.job import ConfirmationResult, Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.services.level2.scanner import Level2Scanner
from monik.services.observability.logging import get_logger, log_fields
from monik.services.resources.dedup import InFlightRegistry

__all__ = ["Level2Worker"]

_LOGGER = get_logger("services.level2.worker")

#: Обработчик завершённой проверки (например, постановка уведомления).
ConfirmationHandler = Callable[[Opportunity, ConfirmationResult], Awaitable[None]]


class Level2Worker:
    """Принимает Job от Level 1 и выполняет подтверждение с ограничением параллелизма.

    Реализует порт ``Level2Dispatcher`` Level 1: передача происходит
    немедленно, без ожидания следующего цикла
    (``02_LEVEL1_SCANNER.md`` §46).
    """

    def __init__(
        self,
        scanner: Level2Scanner,
        config: Level2Config,
        *,
        on_confirmation: ConfirmationHandler | None = None,
    ) -> None:
        self._scanner = scanner
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_parallel)
        self._in_flight = InFlightRegistry()
        self._tasks: set[asyncio.Task[ConfirmationResult]] = set()
        self._on_confirmation = on_confirmation
        self.results: list[ConfirmationResult] = []
        self.rejected_submissions = 0

    @property
    def merged_workflows(self) -> int:
        """Сколько одинаковых workflow было объединено (``CLAUDE.md`` §19)."""
        return self._in_flight.merged_count

    @property
    def active(self) -> int:
        """Сколько подтверждений выполняется сейчас."""
        return len(self._tasks)

    def available_capacity(self) -> int:
        """Сколько Job ещё принимается (backpressure, ``03`` §69)."""
        return max(self._config.queue_capacity - len(self._tasks), 0)

    async def submit(self, opportunity: Opportunity, job: Level2Job) -> None:
        """Принять Job на подтверждение.

        Переполненная очередь не растёт бесконечно: лишний Job отклоняется,
        а не ставится в неограниченную очередь (``03`` §69).
        """
        if self.available_capacity() <= 0:
            self.rejected_submissions += 1
            raise ResourceError(
                f"level 2 queue is full ({self._config.queue_capacity} jobs)",
                subsystem="level2",
                operation="submit",
            )
        task: asyncio.Task[ConfirmationResult] = asyncio.ensure_future(self._run(opportunity, job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> tuple[ConfirmationResult, ...]:
        """Дождаться завершения принятых Job."""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        return tuple(self.results)

    async def cancel_all(self) -> None:
        """Отменить принятые Job (shutdown, ``03`` §73)."""
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def _run(self, opportunity: Opportunity, job: Level2Job) -> ConfirmationResult:
        """Выполнить проверку, объединив одинаковые активные workflow."""
        key = str(job.k_id)
        async with self._semaphore:
            result = await self._in_flight.run(key, lambda: self._confirm(opportunity, job))
        return result

    async def _confirm(self, opportunity: Opportunity, job: Level2Job) -> ConfirmationResult:
        try:
            result = await self._scanner.confirm(job)
        except MonikError as error:
            _LOGGER.error(
                "level 2 confirmation failed",
                extra=log_fields(
                    k_id=str(job.k_id),
                    error_category=error.info.category.value,
                    error_code=error.info.code,
                ),
            )
            raise
        self.results.append(result)
        if self._on_confirmation is not None:
            await self._on_confirmation(opportunity, result)
        return result
