"""Регистрация задач планировщика и порядок их старта.

Scheduler координирует запуск, но не содержит business logic
(``14_SCHEDULER.md`` §3): конкретное действие задаётся обработчиком
соответствующей подсистемы.

Зависимости старта определяются явно (``14_SCHEDULER.md`` §36):
Resource Manager → Registries → Fee System → Capability → Scanners.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import time, timedelta

from monik.config.sections.scheduler import SchedulerConfig, TaskScheduleConfig
from monik.domain.enums.resources import RequestPriority
from monik.domain.enums.scheduler import TaskMode
from monik.domain.errors import ConfigurationError
from monik.domain.models.scheduler import SchedulerTask

__all__ = ["RegisteredTask", "TaskRegistry", "startup_order"]

#: Действие задачи. Планировщик о его содержимом ничего не знает.
TaskHandler = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RegisteredTask:
    """Задача вместе с её обработчиком и зависимостями."""

    task: SchedulerTask
    handler: TaskHandler
    depends_on: tuple[str, ...] = ()
    timeout: timedelta | None = None


@dataclass
class TaskRegistry:
    """Набор задач планировщика."""

    tasks: dict[str, RegisteredTask] = field(default_factory=dict)

    def register(
        self,
        task_id: str,
        handler: TaskHandler,
        *,
        config: SchedulerConfig,
        default: TaskScheduleConfig,
        priority: RequestPriority = RequestPriority.MAINTENANCE,
        depends_on: tuple[str, ...] = (),
        timeout: timedelta | None = None,
    ) -> RegisteredTask:
        """Зарегистрировать задачу.

        Расписание берётся из конфигурации пользователя, а ``default``
        используется, если задача там не описана
        (``14_SCHEDULER.md`` §58-59).
        """
        if task_id in self.tasks:
            raise ConfigurationError(f"scheduler task {task_id} is already registered")
        schedule = config.tasks.get(task_id, default)
        registered = RegisteredTask(
            task=_build_task(task_id, schedule, priority=priority),
            handler=handler,
            depends_on=depends_on,
            timeout=timeout,
        )
        self.tasks[task_id] = registered
        return registered

    def get(self, task_id: str) -> RegisteredTask | None:
        """Найти зарегистрированную задачу."""
        return self.tasks.get(task_id)

    def enabled(self) -> tuple[RegisteredTask, ...]:
        """Включённые задачи в порядке регистрации."""
        return tuple(item for item in self.tasks.values() if item.task.enabled)

    def startup_tasks(self) -> tuple[RegisteredTask, ...]:
        """Startup-задачи в порядке зависимостей."""
        startup = [item for item in self.enabled() if item.task.mode is TaskMode.STARTUP]
        return startup_order(startup)


def _build_task(
    task_id: str, schedule: TaskScheduleConfig, *, priority: RequestPriority
) -> SchedulerTask:
    """Построить доменную задачу из конфигурации расписания."""
    at_time = None
    if schedule.time is not None:
        hour, minute = (int(part) for part in schedule.time.split(":"))
        at_time = time(hour=hour, minute=minute)
    return SchedulerTask(
        task_id=task_id,
        mode=schedule.mode,
        enabled=schedule.enabled,
        overlap_policy=schedule.overlap_policy,
        priority=priority,
        interval=(
            timedelta(seconds=schedule.interval_seconds)
            if schedule.interval_seconds is not None
            else None
        ),
        interval_days=schedule.interval_days,
        at_time=at_time,
        timezone_name=schedule.timezone,
    )


def startup_order(tasks: list[RegisteredTask]) -> tuple[RegisteredTask, ...]:
    """Упорядочить задачи по зависимостям (``14_SCHEDULER.md`` §36).

    Циклическая зависимость — ошибка конфигурации, а не повод запустить
    задачи в произвольном порядке.
    """
    by_id = {item.task.task_id: item for item in tasks}
    ordered: list[RegisteredTask] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ConfigurationError(f"scheduler startup dependency cycle at {task_id}")
        item = by_id.get(task_id)
        if item is None:
            return
        visiting.add(task_id)
        for dependency in item.depends_on:
            visit(dependency)
        visiting.discard(task_id)
        visited.add(task_id)
        ordered.append(item)

    for item in tasks:
        visit(item.task.task_id)
    return tuple(ordered)
