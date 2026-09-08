"""Scheduler: описание задачи и запись о её запуске."""

from __future__ import annotations

from datetime import time, timedelta
from typing import Any, Self

from pydantic import Field, model_validator

from monik.domain.enums.lifecycle import TaskExecutionStatus
from monik.domain.enums.resources import RequestPriority
from monik.domain.enums.scheduler import OverlapPolicy, TaskMode
from monik.domain.models.base import DomainModel
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["SchedulerExecution", "SchedulerTask", "SchedulerTaskState"]


class SchedulerTask(DomainModel):
    """Зарегистрированная задача планировщика (``36_DATA_MODELS.md`` §57).

    Scheduler координирует время запуска, но не содержит business logic
    (``14_SCHEDULER.md`` §3).
    """

    task_id: str = Field(min_length=1, max_length=64)
    mode: TaskMode
    enabled: bool = True
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    priority: RequestPriority = RequestPriority.MAINTENANCE
    interval: timedelta | None = None
    interval_days: int | None = Field(default=None, ge=1)
    at_time: time | None = None
    timezone_name: str | None = Field(default=None, min_length=1, max_length=64)
    max_attempts: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Набор полей обязан соответствовать выбранному режиму."""
        if self.mode is TaskMode.INTERVAL:
            if self.interval is None or self.interval <= timedelta(0):
                raise ValueError("INTERVAL task requires a positive interval")
        elif self.interval is not None:
            raise ValueError(f"interval is not applicable to {self.mode.value} task")
        if self.mode is TaskMode.DAILY:
            if self.at_time is None:
                raise ValueError("DAILY task requires at_time")
            if self.timezone_name is None:
                raise ValueError("DAILY task requires an explicit timezone")
        elif self.at_time is not None:
            raise ValueError(f"at_time is not applicable to {self.mode.value} task")
        return self


class SchedulerExecution(DomainModel):
    """Запись об одном запуске задачи (``36_DATA_MODELS.md`` §58)."""

    execution_id: str = Field(min_length=1, max_length=64)
    task_id: str = Field(min_length=1, max_length=64)
    status: TaskExecutionStatus
    scheduled_for: UtcDatetime
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None
    error_code: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.finished_at is not None and self.started_at is None:
            raise ValueError("execution cannot finish without having started")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("execution finished_at must not precede started_at")
        return self


class SchedulerTaskState(DomainModel):
    """Сохранённое состояние задачи планировщика.

    Хранится минимум, необходимый для восстановления расписания после
    рестарта (``30_DATABASE_SCHEMA.md`` §53, ``14_SCHEDULER.md`` §57).
    """

    task_id: str = Field(min_length=1, max_length=64)
    mode: TaskMode
    enabled: bool = True
    schedule: dict[str, Any] = Field(default_factory=dict)
    last_run_at: UtcDatetime | None = None
    next_run_at: UtcDatetime | None = None
