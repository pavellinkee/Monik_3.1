"""Хранилище состояния планировщика."""

from __future__ import annotations

import aiosqlite

from monik.domain.enums.lifecycle import TaskExecutionStatus
from monik.domain.enums.scheduler import TaskMode
from monik.domain.models.scheduler import SchedulerExecution, SchedulerTaskState
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import from_json, from_timestamp, to_json, to_timestamp
from monik.repositories.sqlite.mapping import column, optional_column

__all__ = ["SchedulerTaskState", "SqliteSchedulerRepository"]


class SqliteSchedulerRepository:
    """Persistence задач и их запусков."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert_task(self, state: SchedulerTaskState, *, updated_at: UtcDatetime) -> None:
        """Сохранить или обновить задачу."""
        await self._database.execute(
            "INSERT INTO scheduler_tasks (task_id, mode, enabled, schedule_json, last_run_at, "
            "next_run_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET mode = excluded.mode, "
            "enabled = excluded.enabled, schedule_json = excluded.schedule_json, "
            "last_run_at = excluded.last_run_at, next_run_at = excluded.next_run_at, "
            "updated_at = excluded.updated_at",
            (
                state.task_id,
                state.mode.value,
                1 if state.enabled else 0,
                to_json(state.schedule),
                to_timestamp(state.last_run_at) if state.last_run_at else None,
                to_timestamp(state.next_run_at) if state.next_run_at else None,
                to_timestamp(updated_at),
            ),
        )

    async def get_task(self, task_id: str) -> SchedulerTaskState | None:
        """Найти задачу по идентификатору."""
        row = await self._database.fetch_one(
            "SELECT task_id, mode, enabled, schedule_json, last_run_at, next_run_at "
            "FROM scheduler_tasks WHERE task_id = ?",
            (task_id,),
        )
        return self._task_to_domain(row) if row else None

    async def list_enabled(self) -> tuple[SchedulerTaskState, ...]:
        """Все включённые задачи."""
        rows = await self._database.fetch_all(
            "SELECT task_id, mode, enabled, schedule_json, last_run_at, next_run_at "
            "FROM scheduler_tasks WHERE enabled = 1 ORDER BY task_id"
        )
        return tuple(self._task_to_domain(row) for row in rows)

    async def record_execution(self, execution: SchedulerExecution) -> None:
        """Сохранить запись о запуске задачи."""
        await self._database.execute(
            "INSERT INTO scheduler_executions (execution_id, task_id, status, scheduled_for, "
            "started_at, finished_at, error_code) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(execution_id) DO UPDATE SET status = excluded.status, "
            "started_at = excluded.started_at, finished_at = excluded.finished_at, "
            "error_code = excluded.error_code",
            (
                execution.execution_id,
                execution.task_id,
                execution.status.value,
                to_timestamp(execution.scheduled_for),
                to_timestamp(execution.started_at) if execution.started_at else None,
                to_timestamp(execution.finished_at) if execution.finished_at else None,
                execution.error_code,
            ),
        )

    async def last_execution(self, task_id: str) -> SchedulerExecution | None:
        """Последний зарегистрированный запуск задачи."""
        row = await self._database.fetch_one(
            "SELECT execution_id, task_id, status, scheduled_for, started_at, finished_at, "
            "error_code FROM scheduler_executions WHERE task_id = ? "
            "ORDER BY scheduled_for DESC LIMIT 1",
            (task_id,),
        )
        return self._execution_to_domain(row) if row else None

    async def delete_executions_before(self, moment: UtcDatetime) -> int:
        """Удалить устаревшие записи о запусках."""
        rows = await self._database.fetch_all(
            "SELECT execution_id FROM scheduler_executions WHERE scheduled_for < ?",
            (to_timestamp(moment),),
        )
        if not rows:
            return 0
        await self._database.execute(
            "DELETE FROM scheduler_executions WHERE scheduled_for < ?",
            (to_timestamp(moment),),
        )
        return len(rows)

    @staticmethod
    def _task_to_domain(row: aiosqlite.Row) -> SchedulerTaskState:
        last_run_at = optional_column(row, "last_run_at")
        next_run_at = optional_column(row, "next_run_at")
        schedule = from_json(str(column(row, "schedule_json")))
        return SchedulerTaskState(
            task_id=str(column(row, "task_id")),
            mode=TaskMode(str(column(row, "mode"))),
            enabled=bool(column(row, "enabled")),
            schedule=schedule if isinstance(schedule, dict) else {},
            last_run_at=from_timestamp(str(last_run_at)) if last_run_at else None,
            next_run_at=from_timestamp(str(next_run_at)) if next_run_at else None,
        )

    @staticmethod
    def _execution_to_domain(row: aiosqlite.Row) -> SchedulerExecution:
        started_at = optional_column(row, "started_at")
        finished_at = optional_column(row, "finished_at")
        return SchedulerExecution(
            execution_id=str(column(row, "execution_id")),
            task_id=str(column(row, "task_id")),
            status=TaskExecutionStatus(str(column(row, "status"))),
            scheduled_for=from_timestamp(str(column(row, "scheduled_for"))),
            started_at=from_timestamp(str(started_at)) if started_at else None,
            finished_at=from_timestamp(str(finished_at)) if finished_at else None,
            error_code=optional_column(row, "error_code"),
        )
