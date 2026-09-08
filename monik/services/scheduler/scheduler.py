"""Планировщик задач Monik.

Scheduler координирует **когда** выполнять задачу и не содержит business
logic (``14_SCHEDULER.md`` §3). Он же отвечает за порядок старта (§36),
overlap policy (§27), missed-run policy (§33-34), cancellation (§49) и
изоляцию сбоев (§43).

Расписания задач независимы (§21): задержка одной задачи не сдвигает
остальные.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from monik.domain.enums.lifecycle import TaskExecutionStatus
from monik.domain.enums.scheduler import OverlapPolicy, TaskMode
from monik.domain.models.scheduler import (
    SchedulerExecution,
    SchedulerTask,
    SchedulerTaskState,
)
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields
from monik.services.scheduler.registry import RegisteredTask, TaskRegistry
from monik.services.scheduler.runner import ExecutionOutcome, TaskRunner
from monik.services.scheduler.timing import next_run_at

__all__ = ["ExecutionLog", "Scheduler"]

_LOGGER = get_logger("services.scheduler")


@runtime_checkable
class ExecutionLog(Protocol):
    """Персистентное расписание и журнал запусков (``14_SCHEDULER.md`` §57)."""

    async def upsert_task(self, state: SchedulerTaskState, *, updated_at: datetime) -> None:
        """Сохранить состояние задачи."""
        ...

    async def record_execution(self, execution: SchedulerExecution) -> None:
        """Сохранить запись о запуске."""
        ...

    async def last_execution(self, task_id: str) -> SchedulerExecution | None:
        """Последний запуск задачи."""
        ...


@dataclass
class Scheduler:
    """Определяет момент запуска задач и выполняет их."""

    registry: TaskRegistry
    runner: TaskRunner
    clock: Clock
    log: ExecutionLog | None = None
    _next_runs: dict[str, datetime] = field(default_factory=dict)
    _startup_done: set[str] = field(default_factory=set)

    def next_run(self, task_id: str) -> datetime | None:
        """Запланированный момент следующего запуска."""
        return self._next_runs.get(task_id)

    async def prepare(self) -> None:
        """Рассчитать расписание после загрузки конфигурации (§35).

        Момент следующего запуска считается от последнего выполнения,
        восстановленного из журнала, поэтому рестарт не приводит к серии
        догоняющих запусков (§34).
        """
        now = self.clock.now()
        for item in self.registry.enabled():
            last_run = await self._last_success(item.task.task_id)
            planned = next_run_at(item.task, now=now, last_run_at=last_run)
            if planned is not None:
                self._next_runs[item.task.task_id] = planned
            await self._persist(item, last_run_at=last_run, next_run_at=planned, now=now)

    async def run_startup(self) -> tuple[ExecutionOutcome, ...]:
        """Выполнить startup-задачи в порядке зависимостей (§36).

        Повторный вызов не запускает startup-задачи заново: после рестарта
        дублирующий startup не создаётся.
        """
        outcomes = []
        for item in self.registry.startup_tasks():
            task_id = item.task.task_id
            if task_id in self._startup_done:
                continue
            outcome = await self._run(item, scheduled_for=self.clock.now())
            self._startup_done.add(task_id)
            outcomes.append(outcome)
            if not outcome.succeeded:
                # Сбой зависимости фиксируется, но остальные задачи
                # продолжают старт (§42-43).
                _LOGGER.error(
                    "startup task failed",
                    extra=log_fields(task=task_id, status=outcome.status.value),
                )
        return tuple(outcomes)

    async def tick(self) -> tuple[ExecutionOutcome, ...]:
        """Выполнить задачи, для которых наступило время запуска."""
        now = self.clock.now()
        outcomes = []
        for item in self.registry.enabled():
            task_id = item.task.task_id
            planned = self._next_runs.get(task_id)
            if planned is None or planned > now:
                continue
            outcome = await self._run(item, scheduled_for=planned)
            outcomes.append(outcome)
            self._reschedule(item, completed_at=self.clock.now())
        return tuple(outcomes)

    async def trigger(self, task_id: str) -> ExecutionOutcome | None:
        """Запустить задачу вручную (§32).

        Ручной запуск подчиняется overlap policy и не создаёт дублирующее
        выполнение, а расписание при этом не сдвигается (§66 доклада о
        manual scan).
        """
        item = self.registry.get(task_id)
        if item is None:
            return None
        return await self._run(item, scheduled_for=self.clock.now())

    async def shutdown(self) -> None:
        """Прекратить запуск новых задач и отменить активные (§49)."""
        self._next_runs.clear()
        await self.runner.cancel_all()

    # --- внутреннее -------------------------------------------------------

    async def _run(self, item: RegisteredTask, *, scheduled_for: datetime) -> ExecutionOutcome:
        outcome = await self.runner.run(item, scheduled_for=scheduled_for)
        if self.log is not None:
            await self.log.record_execution(outcome.execution)
        return outcome

    def _reschedule(self, item: RegisteredTask, *, completed_at: datetime) -> None:
        """Пересчитать момент следующего запуска после выполнения."""
        planned = next_run_at(item.task, now=completed_at, last_run_at=completed_at)
        if planned is None:
            self._next_runs.pop(item.task.task_id, None)
            return
        if item.task.overlap_policy is OverlapPolicy.QUEUE:
            # QUEUE не создаёт бесконечную очередь: следующий запуск всё
            # равно один (``14_SCHEDULER.md`` §53).
            planned = max(planned, completed_at)
        self._next_runs[item.task.task_id] = planned

    async def _persist(
        self,
        item: RegisteredTask,
        *,
        last_run_at: datetime | None,
        next_run_at: datetime | None,
        now: datetime,
    ) -> None:
        """Сохранить состояние задачи: журнал запусков ссылается на неё."""
        if self.log is None:
            return
        await self.log.upsert_task(
            SchedulerTaskState(
                task_id=item.task.task_id,
                mode=item.task.mode,
                enabled=item.task.enabled,
                schedule=_schedule_snapshot(item.task),
                last_run_at=last_run_at,
                next_run_at=next_run_at,
            ),
            updated_at=now,
        )

    async def _last_success(self, task_id: str) -> datetime | None:
        """Момент последнего успешного выполнения из журнала."""
        if self.log is None:
            return None
        execution = await self.log.last_execution(task_id)
        if execution is None or execution.status is not TaskExecutionStatus.SUCCESS:
            return None
        return execution.finished_at or execution.started_at

    def has_startup_tasks(self) -> bool:
        """Есть ли задачи, выполняемые при старте."""
        return any(item.task.mode is TaskMode.STARTUP for item in self.registry.enabled())


def _schedule_snapshot(task: SchedulerTask) -> dict[str, object]:
    """Снимок расписания задачи для persistence."""
    return {
        "overlap_policy": task.overlap_policy.value,
        "priority": task.priority.value,
        "interval_seconds": task.interval.total_seconds() if task.interval else None,
        "interval_days": task.interval_days,
        "at_time": task.at_time.isoformat() if task.at_time else None,
        "timezone": task.timezone_name,
    }
