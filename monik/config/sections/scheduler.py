"""Конфигурация Scheduler."""

from __future__ import annotations

from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.scheduler import OverlapPolicy, TaskMode

__all__ = ["SchedulerConfig", "TaskScheduleConfig"]


class TaskScheduleConfig(ConfigSection):
    """Расписание одной задачи (``17_CONFIGURATION.md`` §44).

    Поддерживаются режимы STARTUP, INTERVAL, DAILY и MANUAL
    (``14_SCHEDULER.md`` §12-15). Для DAILY обязательны время в формате
    ``HH:MM`` и валидная IANA timezone (``17_CONFIGURATION.md`` §18-19).
    """

    enabled: bool = True
    mode: TaskMode
    interval_seconds: int | None = Field(default=None, ge=1, le=86_400)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.mode is TaskMode.INTERVAL and self.interval_seconds is None:
            raise ValueError("INTERVAL task requires interval_seconds")
        if self.mode is not TaskMode.INTERVAL and self.interval_seconds is not None:
            raise ValueError(f"interval_seconds is not applicable to {self.mode.value} task")
        if self.mode is TaskMode.DAILY:
            if self.time is None:
                raise ValueError("DAILY task requires time in HH:MM format")
            if self.timezone is None:
                raise ValueError("DAILY task requires an explicit timezone")
        elif self.time is not None:
            raise ValueError(f"time is not applicable to {self.mode.value} task")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(f"invalid IANA timezone: {self.timezone!r}") from exc
        return self


class SchedulerConfig(ConfigSection):
    """Набор запланированных задач.

    Scheduler координирует запуск, но не содержит business logic
    (``14_SCHEDULER.md`` §3).
    """

    enabled: bool = True
    tasks: dict[str, TaskScheduleConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for task_id in self.tasks:
            if not task_id or len(task_id) > 64:
                raise ValueError(f"invalid scheduler task id: {task_id!r}")
        return self
