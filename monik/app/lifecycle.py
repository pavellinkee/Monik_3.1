"""Жизненный цикл приложения.

Последовательность запуска фиксирована ``CLAUDE.md`` §30:

1. загрузить configuration;
2. открыть SQLite;
3. проверить integrity;
4. выполнить migrations;
5. восстановить незавершённое состояние;
6. инициализировать adapters;
7. инициализировать Resource Manager;
8. инициализировать Scheduler;
9. инициализировать Telegram;
10. запустить workers.

Business logic здесь отсутствует: модуль только связывает готовые
подсистемы и управляет их запуском и остановкой.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from monik.app.container import Container, build_container
from monik.app.recovery import RecoveryReport, RecoveryService
from monik.app.supervisor import SupervisedWorker, Supervisor
from monik.config.loader import LoadedConfiguration
from monik.config.sections.scheduler import TaskScheduleConfig
from monik.domain.enums.health import ApplicationHealthStatus, SupervisorState
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.enums.scheduler import TaskMode
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.services.observability import MetricsRegistry
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields
from monik.services.scheduler import Scheduler, TaskHandler, TaskRegistry, TaskRunner

__all__ = [
    "TASK_CAPABILITY_LOAD",
    "TASK_LEVEL1_SCAN",
    "TASK_NOTIFICATIONS",
    "TASK_TELEGRAM_COMMANDS",
    "Application",
    "build_application",
    "create_application",
]

_LOGGER = get_logger("app.lifecycle")

#: Идентификаторы задач планировщика.
TASK_LEVEL1_SCAN = "level1_scan"
TASK_NOTIFICATIONS = "notification_delivery"
TASK_TELEGRAM_COMMANDS = "telegram_commands"
TASK_CAPABILITY_LOAD = "capability_load"

#: Расписания по умолчанию. Пользовательская конфигурация имеет приоритет
#: (``14_SCHEDULER.md`` §58-59).
_DEFAULT_SCHEDULES: dict[str, TaskScheduleConfig] = {
    TASK_LEVEL1_SCAN: TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=300),
    TASK_NOTIFICATIONS: TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=10),
    TASK_TELEGRAM_COMMANDS: TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=5),
    TASK_CAPABILITY_LOAD: TaskScheduleConfig(mode=TaskMode.STARTUP),
}


@dataclass
class Application:
    """Собранное приложение и его жизненный цикл."""

    container: Container
    scheduler: Scheduler
    supervisor: Supervisor
    recovery: RecoveryService
    shutdown_timeout: timedelta = timedelta(seconds=30)
    recovery_report: RecoveryReport | None = None
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def startup(self) -> RecoveryReport:
        """Выполнить шаги 5-9 последовательности запуска.

        База уже открыта и мигрирована (шаги 2-4 выполняет
        :func:`create_application`), поэтому здесь восстанавливается
        состояние и инициализируются подсистемы.
        """
        health = self.container.health
        health.set_component("configuration", ApplicationHealthStatus.HEALTHY)
        health.set_component("database", ApplicationHealthStatus.HEALTHY)

        report = await self.recovery.recover()
        self.recovery_report = report

        await self.container.capabilities.load()
        health.set_component("resource_manager", ApplicationHealthStatus.HEALTHY)

        await self.scheduler.prepare()
        await self.scheduler.run_startup()
        health.set_component("scheduler", ApplicationHealthStatus.HEALTHY)

        for component in ("level1", "level2", "fees", "calculator", "notifications"):
            health.set_component(component, ApplicationHealthStatus.HEALTHY)
        _LOGGER.info("startup complete", extra=log_fields(recovered=report.total))
        return report

    async def run(self) -> SupervisorState:
        """Запустить воркеры и работать до остановки."""
        self.supervisor.register(
            SupervisedWorker(name="scheduler_loop", run=self._scheduler_loop, critical=True)
        )
        await self.supervisor.start()
        return await self.supervisor.supervise()

    def request_stop(self) -> None:
        """Попросить приложение остановиться."""
        self._stop.set()

    async def shutdown(self) -> None:
        """Graceful shutdown: новые циклы не создаются (``14`` §49)."""
        self.request_stop()
        await self.scheduler.shutdown()
        await self.container.level2_worker.cancel_all()
        try:
            await asyncio.wait_for(
                self.supervisor.shutdown(), timeout=self.shutdown_timeout.total_seconds()
            )
        except TimeoutError:
            _LOGGER.warning("shutdown timed out; workers were cancelled")
        await self.container.aclose()

    async def _scheduler_loop(self) -> None:
        """Периодически выполнять готовые задачи планировщика.

        Собственного расписания цикл не задаёт: моменты запуска определяет
        Scheduler (``14_SCHEDULER.md`` §3, §63).
        """
        interval = 1.0
        while not self._stop.is_set():
            await self.scheduler.tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                continue


def build_application(
    loaded: LoadedConfiguration,
    *,
    database: Database,
    clock: Clock,
    metrics: MetricsRegistry | None = None,
    adapters: dict[ProviderId, AggregatorAdapter] | None = None,
) -> Application:
    """Собрать приложение поверх открытой базы.

    ``adapters`` передаётся composition root'у: это позволяет запустить
    приложение на детерминированных test implementations, не подменяя
    собранные подсистемы после сборки.
    """
    container = build_container(
        loaded, database=database, clock=clock, metrics=metrics, adapters=adapters
    )
    registry = TaskRegistry()
    config = loaded.config

    registry.register(
        TASK_CAPABILITY_LOAD,
        _capability_task(container),
        config=config.scheduler,
        default=_DEFAULT_SCHEDULES[TASK_CAPABILITY_LOAD],
    )
    registry.register(
        TASK_LEVEL1_SCAN,
        _level1_task(container),
        config=config.scheduler,
        default=_DEFAULT_SCHEDULES[TASK_LEVEL1_SCAN],
        priority=RequestPriority.LEVEL1_BUY,
        timeout=timedelta(seconds=config.scanner.level1.scan_timeout_seconds),
    )
    registry.register(
        TASK_NOTIFICATIONS,
        _notification_task(container),
        config=config.scheduler,
        default=_DEFAULT_SCHEDULES[TASK_NOTIFICATIONS],
    )
    if container.commands is not None:
        registry.register(
            TASK_TELEGRAM_COMMANDS,
            _command_task(container),
            config=config.scheduler,
            default=_DEFAULT_SCHEDULES[TASK_TELEGRAM_COMMANDS],
            priority=RequestPriority.BACKGROUND,
        )

    scheduler = Scheduler(
        registry=registry,
        runner=TaskRunner(clock, container.metrics),
        clock=clock,
        log=container.repositories.scheduler,
    )
    supervisor = Supervisor(monitor=container.health, clock=clock, config=config.health)
    recovery = RecoveryService(
        jobs=container.repositories.jobs,
        opportunities=container.repositories.opportunities,
        notifications=container.repositories.notifications,
        clock=clock,
        transitions=container.transitions,
    )
    return Application(
        container=container,
        scheduler=scheduler,
        supervisor=supervisor,
        recovery=recovery,
        shutdown_timeout=timedelta(seconds=config.application.shutdown_timeout_seconds),
    )


async def create_application(
    loaded: LoadedConfiguration,
    *,
    clock: Clock,
    metrics: MetricsRegistry | None = None,
    adapters: dict[ProviderId, AggregatorAdapter] | None = None,
) -> tuple[Application, Database]:
    """Выполнить шаги 2-4 запуска и собрать приложение.

    SQLite открывается, проверяется её целостность и применяются
    migrations — до любых подсистем (``CLAUDE.md`` §30).
    """
    database = Database(loaded.config.database)
    await database.connect()
    await MigrationRunner(database).upgrade()
    application = build_application(
        loaded, database=database, clock=clock, metrics=metrics, adapters=adapters
    )
    return application, database


def _capability_task(container: Container) -> TaskHandler:
    """Загрузка сохранённого состояния capability при старте.

    Полный discovery здесь не выполняется: он относится к maintenance
    (``08_CAPABILITY_REGISTRY.md`` §3-4).
    """

    async def run() -> None:
        await container.capabilities.load()

    return run


def _level1_task(container: Container) -> TaskHandler:
    async def run() -> None:
        await container.level1.scan()

    return run


def _notification_task(container: Container) -> TaskHandler:
    async def run() -> None:
        await container.notifications.dispatch_pending()

    return run


def _command_task(container: Container) -> TaskHandler:
    async def run() -> None:
        if container.commands is not None:
            await container.commands.poll_once()

    return run
