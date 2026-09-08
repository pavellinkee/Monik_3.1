"""Supervisor: контроль воркеров и безопасная остановка.

Supervisor контролирует Level 1, Level 2, Resource Manager, Telegram,
Maintenance и Scheduler (``CLAUDE.md`` §34). При падении некритического
worker'а выполняется попытка восстановить именно его; критическая ошибка
persistence переводит систему в ``SAFE_STOP``.

Supervisor не содержит бизнес-логики: он запускает переданные корутины и
следит за их состоянием.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from monik.config.sections.health import HealthConfig
from monik.domain.enums.health import ApplicationHealthStatus, SupervisorState
from monik.domain.errors import DatabaseError
from monik.services.health.monitor import HealthMonitor
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["SupervisedWorker", "Supervisor"]

_LOGGER = get_logger("app.supervisor")

#: Работа воркера. Supervisor о её содержимом ничего не знает.
WorkerRun = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SupervisedWorker:
    """Описание контролируемого worker'а."""

    name: str
    run: WorkerRun
    critical: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("supervised worker requires a name")


@dataclass
class Supervisor:
    """Запускает воркеры и реагирует на их падение."""

    monitor: HealthMonitor
    clock: Clock
    config: HealthConfig = field(default_factory=HealthConfig)
    state: SupervisorState = SupervisorState.STARTING
    restarts: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    _workers: dict[str, SupervisedWorker] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    def register(self, worker: SupervisedWorker) -> None:
        """Зарегистрировать worker до запуска."""
        if worker.name in self._workers:
            raise ValueError(f"worker {worker.name} is already registered")
        self._workers[worker.name] = worker
        self.monitor.set_component(worker.name, ApplicationHealthStatus.STARTING)

    async def start(self) -> None:
        """Запустить все зарегистрированные воркеры."""
        self.state = SupervisorState.RUNNING
        for worker in self._workers.values():
            self._spawn(worker)

    async def supervise(self) -> SupervisorState:
        """Дождаться завершения воркеров, восстанавливая упавшие.

        Возвращает итоговое состояние: ``SAFE_STOP`` означает, что работа
        прекращена из-за критической ошибки.
        """
        while self._tasks and self.state is not SupervisorState.SAFE_STOP:
            done, _ = await asyncio.wait(
                tuple(self._tasks.values()), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                name = self._name_of(task)
                if name is None:  # pragma: no cover - защита от рассинхронизации
                    continue
                self._tasks.pop(name, None)
                await self._handle_completion(name, task)
        if self.state is not SupervisorState.SAFE_STOP:
            self.state = SupervisorState.STOPPED
        return self.state

    async def shutdown(self) -> None:
        """Остановить воркеры (graceful shutdown)."""
        self.monitor.mark_stopping()
        for task in tuple(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        self._tasks.clear()
        if self.state is not SupervisorState.SAFE_STOP:
            self.state = SupervisorState.STOPPED

    # --- внутреннее -------------------------------------------------------

    def _spawn(self, worker: SupervisedWorker) -> None:
        task: asyncio.Task[None] = asyncio.ensure_future(worker.run())
        self._tasks[worker.name] = task
        self.monitor.set_component(worker.name, ApplicationHealthStatus.HEALTHY)

    async def _handle_completion(self, name: str, task: asyncio.Task[None]) -> None:
        worker = self._workers[name]
        if task.cancelled():
            self.monitor.set_component(name, ApplicationHealthStatus.STOPPING)
            return
        error = task.exception()
        if error is None:
            self.monitor.set_component(name, ApplicationHealthStatus.STOPPING)
            return
        await self._handle_failure(worker, error)

    async def _handle_failure(self, worker: SupervisedWorker, error: BaseException) -> None:
        self.failures[worker.name] = type(error).__name__
        if isinstance(error, DatabaseError):
            # Критическая ошибка persistence: продолжать работу с
            # недостоверным состоянием запрещено (``CLAUDE.md`` §34).
            _LOGGER.error(
                "critical persistence failure: entering SAFE_STOP",
                extra=log_fields(worker=worker.name, error=type(error).__name__),
            )
            self.monitor.set_component(
                worker.name, ApplicationHealthStatus.UNAVAILABLE, reason="persistence failure"
            )
            await self._safe_stop()
            return

        if worker.critical:
            _LOGGER.error(
                "critical worker failed",
                extra=log_fields(worker=worker.name, error=type(error).__name__),
            )
            self.monitor.set_component(
                worker.name, ApplicationHealthStatus.UNAVAILABLE, reason=str(error)[:200]
            )
            await self._safe_stop()
            return

        attempts = self.restarts.get(worker.name, 0)
        if attempts >= self.config.worker_restart_limit:
            _LOGGER.error(
                "worker restart limit reached",
                extra=log_fields(worker=worker.name, attempts=attempts),
            )
            self.monitor.set_component(
                worker.name, ApplicationHealthStatus.UNAVAILABLE, reason="restart limit reached"
            )
            self.state = SupervisorState.DEGRADED
            return

        self.restarts[worker.name] = attempts + 1
        _LOGGER.warning(
            "restarting worker",
            extra=log_fields(worker=worker.name, attempt=attempts + 1),
        )
        self.monitor.set_component(
            worker.name, ApplicationHealthStatus.DEGRADED, reason="restarting"
        )
        self.state = SupervisorState.DEGRADED
        self._spawn(worker)

    async def _safe_stop(self) -> None:
        """Перевести систему в ``SAFE_STOP`` и остановить воркеры."""
        self.state = SupervisorState.SAFE_STOP
        self.monitor.mark_stopping()
        for task in tuple(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks.values()), return_exceptions=True)
        self._tasks.clear()

    def _name_of(self, task: asyncio.Task[None]) -> str | None:
        """Имя worker'а по его задаче."""
        for name, candidate in self._tasks.items():
            if candidate is task:
                return name
        return None
