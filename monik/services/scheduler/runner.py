"""Выполнение одной задачи планировщика.

Overlap policy определяется задачей (``14_SCHEDULER.md`` §27): для Level 1
по умолчанию ``SKIP``, чтобы одинаковые циклы не накапливались (§28).

Истечение timeout не означает автоматический бесконечный retry (§51):
задача получает статус неудачи, а повторение определяется policy.

Сбой одной задачи не останавливает остальные (§43).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime

from monik.domain.enums.lifecycle import TaskExecutionStatus
from monik.domain.enums.scheduler import OverlapPolicy
from monik.domain.errors import MonikError
from monik.domain.models.scheduler import SchedulerExecution
from monik.services.observability import names
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields
from monik.services.observability.metrics import MetricsRegistry
from monik.services.scheduler.registry import RegisteredTask

__all__ = ["ExecutionOutcome", "TaskRunner"]

_LOGGER = get_logger("services.scheduler.runner")


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """Итог одного запуска задачи."""

    execution: SchedulerExecution
    error: BaseException | None = None

    @property
    def status(self) -> TaskExecutionStatus:
        """Статус запуска."""
        return self.execution.status

    @property
    def succeeded(self) -> bool:
        """Успешно ли выполнена задача."""
        return self.execution.status is TaskExecutionStatus.SUCCESS


class TaskRunner:
    """Запускает задачи, соблюдая overlap policy и timeout."""

    def __init__(self, clock: Clock, metrics: MetricsRegistry | None = None) -> None:
        self._clock = clock
        self._metrics = metrics
        self._running: dict[str, asyncio.Task[None]] = {}

    def is_running(self, task_id: str) -> bool:
        """Выполняется ли задача сейчас."""
        return task_id in self._running

    @property
    def running_tasks(self) -> tuple[str, ...]:
        """Идентификаторы выполняющихся задач."""
        return tuple(self._running)

    async def run(self, item: RegisteredTask, *, scheduled_for: datetime) -> ExecutionOutcome:
        """Выполнить задачу и вернуть запись о запуске."""
        task_id = item.task.task_id
        if self.is_running(task_id) and item.task.overlap_policy is OverlapPolicy.SKIP:
            # Накопление одинаковых запусков предотвращается (§28-30).
            _LOGGER.info("task run skipped: previous run is active", extra=log_fields(task=task_id))
            return ExecutionOutcome(
                execution=self._execution(
                    item, scheduled_for, TaskExecutionStatus.SKIPPED, started_at=None
                )
            )

        started_at = self._clock.now()
        with log_context(operation=task_id):
            return await self._execute(item, scheduled_for=scheduled_for, started_at=started_at)

    async def cancel_all(self) -> None:
        """Отменить выполняющиеся задачи (graceful shutdown, §49)."""
        for task in tuple(self._running.values()):
            task.cancel()
        if self._running:
            await asyncio.gather(*tuple(self._running.values()), return_exceptions=True)
        self._running.clear()

    async def _execute(
        self, item: RegisteredTask, *, scheduled_for: datetime, started_at: datetime
    ) -> ExecutionOutcome:
        task_id = item.task.task_id
        running: asyncio.Task[None] = asyncio.ensure_future(item.handler())
        self._running[task_id] = running
        try:
            if item.timeout is not None:
                await asyncio.wait_for(running, timeout=item.timeout.total_seconds())
            else:
                await running
        except TimeoutError:
            # Timeout не превращается в бесконечный retry (§51).
            running.cancel()
            _LOGGER.warning("task timed out", extra=log_fields(task=task_id))
            return self._finish(
                item, scheduled_for, started_at, TaskExecutionStatus.FAILED, "task_timeout"
            )
        except asyncio.CancelledError:
            if not running.cancelled():
                # Отменили сам вызывающий: отмена должна распространиться
                # дальше, а не превратиться в результат выполнения.
                raise
            _LOGGER.info("task cancelled", extra=log_fields(task=task_id))
            return self._finish(
                item, scheduled_for, started_at, TaskExecutionStatus.CANCELLED, "cancelled"
            )
        except MonikError as error:
            # Сбой одной задачи не останавливает планировщик (§43).
            _LOGGER.error(
                "task failed",
                extra=log_fields(task=task_id, error_category=error.info.category.value),
            )
            return self._finish(
                item, scheduled_for, started_at, TaskExecutionStatus.FAILED, error.info.code, error
            )
        except Exception as error:  # noqa: BLE001 - изоляция сбоя задачи
            _LOGGER.error(
                "task raised an unexpected error",
                extra=log_fields(task=task_id, error=type(error).__name__),
            )
            return self._finish(
                item, scheduled_for, started_at, TaskExecutionStatus.FAILED, "internal_error", error
            )
        finally:
            self._running.pop(task_id, None)

        return self._finish(item, scheduled_for, started_at, TaskExecutionStatus.SUCCESS, None)

    def _finish(
        self,
        item: RegisteredTask,
        scheduled_for: datetime,
        started_at: datetime,
        status: TaskExecutionStatus,
        error_code: str | None,
        error: BaseException | None = None,
    ) -> ExecutionOutcome:
        finished_at = self._clock.now()
        execution = SchedulerExecution(
            execution_id=str(uuid.uuid4()),
            task_id=item.task.task_id,
            status=status,
            scheduled_for=scheduled_for,
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
        )
        if self._metrics is not None:
            # Идентификатор задачи — low-cardinality label (``28`` §41).
            self._metrics.increment(
                names.SCHEDULER_EXECUTIONS, task=item.task.task_id, status=status.value
            )
            self._metrics.observe(
                names.SCHEDULER_SECONDS,
                (finished_at - started_at).total_seconds(),
                task=item.task.task_id,
            )
        return ExecutionOutcome(execution=execution, error=error)

    def _execution(
        self,
        item: RegisteredTask,
        scheduled_for: datetime,
        status: TaskExecutionStatus,
        *,
        started_at: datetime | None,
    ) -> SchedulerExecution:
        now = self._clock.now()
        return SchedulerExecution(
            execution_id=str(uuid.uuid4()),
            task_id=item.task.task_id,
            status=status,
            scheduled_for=scheduled_for,
            started_at=started_at,
            finished_at=now if started_at is not None else None,
        )
