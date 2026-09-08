"""Scheduler: расчёт времени, overlap, startup, отмена и изоляция сбоев.

Покрывает ``14_SCHEDULER.md`` и обязательные тесты плана S17.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from monik.config.sections.scheduler import SchedulerConfig, TaskScheduleConfig
from monik.domain.enums.lifecycle import TaskExecutionStatus
from monik.domain.enums.resources import RequestPriority
from monik.domain.enums.scheduler import OverlapPolicy, TaskMode
from monik.domain.errors import ConfigurationError, ProviderError
from monik.domain.models.scheduler import (
    SchedulerExecution,
    SchedulerTask,
    SchedulerTaskState,
)
from monik.services.observability import FakeClock
from monik.services.scheduler import (
    RegisteredTask,
    Scheduler,
    TaskRegistry,
    TaskRunner,
    local_run_instant,
    next_run_at,
    startup_order,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def interval_task(
    task_id: str = "level1_scan",
    *,
    seconds: int = 300,
    overlap: OverlapPolicy = OverlapPolicy.SKIP,
) -> SchedulerTask:
    return SchedulerTask(
        task_id=task_id,
        mode=TaskMode.INTERVAL,
        interval=timedelta(seconds=seconds),
        overlap_policy=overlap,
        priority=RequestPriority.LEVEL1_BUY,
    )


def daily_task(
    task_id: str = "maintenance",
    *,
    at: time = time(3, 30),
    timezone_name: str = "Europe/Lisbon",
    interval_days: int | None = None,
) -> SchedulerTask:
    return SchedulerTask(
        task_id=task_id,
        mode=TaskMode.DAILY,
        at_time=at,
        timezone_name=timezone_name,
        interval_days=interval_days,
    )


# --- расчёт времени -------------------------------------------------------


def test_interval_task_runs_immediately_when_never_executed() -> None:
    assert next_run_at(interval_task(), now=NOW) == NOW


def test_interval_task_is_scheduled_from_the_last_run() -> None:
    planned = next_run_at(interval_task(seconds=300), now=NOW, last_run_at=NOW)
    assert planned == NOW + timedelta(seconds=300)


def test_missed_intervals_do_not_create_a_backlog() -> None:
    """Пропущенные интервалы дают один запуск, а не серию (§34, §53)."""
    long_ago = NOW - timedelta(hours=5)
    planned = next_run_at(interval_task(seconds=300), now=NOW, last_run_at=long_ago)
    assert planned == NOW


def test_daily_task_runs_at_the_configured_local_time() -> None:
    """Ежедневная задача запускается в заданное локальное время (§7, §9)."""
    planned = next_run_at(daily_task(at=time(3, 30)), now=NOW)
    assert planned is not None
    assert planned > NOW
    # 03:30 в Лиссабоне зимой совпадает с UTC.
    assert planned == datetime(2026, 1, 2, 3, 30, tzinfo=UTC)


def test_daily_task_respects_interval_days() -> None:
    planned = next_run_at(daily_task(at=time(3, 30), interval_days=3), now=NOW, last_run_at=NOW)
    assert planned == datetime(2026, 1, 4, 3, 30, tzinfo=UTC)


def test_daily_time_is_not_a_fixed_utc_offset() -> None:
    """Летом то же локальное время соответствует другому UTC (§10)."""
    summer = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    planned = next_run_at(daily_task(at=time(3, 30)), now=summer)
    assert planned is not None
    # Лиссабон летом — UTC+1, поэтому 03:30 локального времени = 02:30 UTC.
    assert planned == datetime(2026, 7, 2, 2, 30, tzinfo=UTC)


def test_dst_spring_forward_gap_runs_after_the_transition() -> None:
    """Несуществующее локальное время не пропускает запуск (§10).

    В Лиссабоне 29 марта 2026 часы переводятся с 01:00 на 02:00, поэтому
    01:30 не существует. Запуск сдвигается вперёд на величину перехода и
    происходит в 02:30 по местному времени.
    """
    instant = local_run_instant(datetime(2026, 3, 29).date(), time(1, 30), "Europe/Lisbon")
    assert instant == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert instant.astimezone(ZoneInfo("Europe/Lisbon")).hour == 2


def test_dst_fall_back_uses_the_first_occurrence() -> None:
    """Неоднозначное локальное время выполняется один раз (§10)."""
    instant = local_run_instant(datetime(2026, 10, 25).date(), time(1, 30), "Europe/Lisbon")
    assert instant == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def test_startup_and_manual_tasks_have_no_schedule() -> None:
    """STARTUP и MANUAL собственного расписания не имеют (§13, §15)."""
    startup = SchedulerTask(task_id="startup", mode=TaskMode.STARTUP)
    manual = SchedulerTask(task_id="manual", mode=TaskMode.MANUAL)
    assert next_run_at(startup, now=NOW) is None
    assert next_run_at(manual, now=NOW) is None


def test_disabled_task_is_never_scheduled() -> None:
    disabled = interval_task().replace(enabled=False)
    assert next_run_at(disabled, now=NOW) is None


# --- выполнение и overlap -------------------------------------------------


def registered(
    task: SchedulerTask,
    handler: object,
    *,
    depends_on: tuple[str, ...] = (),
    timeout: timedelta | None = None,
) -> RegisteredTask:
    return RegisteredTask(
        task=task,
        handler=handler,  # type: ignore[arg-type]
        depends_on=depends_on,
        timeout=timeout,
    )


async def test_successful_run_is_recorded(clock: FakeClock) -> None:
    calls: list[int] = []

    async def handler() -> None:
        calls.append(1)

    runner = TaskRunner(clock)
    outcome = await runner.run(registered(interval_task(), handler), scheduled_for=NOW)

    assert outcome.succeeded
    assert outcome.execution.status is TaskExecutionStatus.SUCCESS
    assert calls == [1]


async def test_overlapping_run_is_skipped(clock: FakeClock) -> None:
    """Level 1 по умолчанию пропускает наложенный запуск (§28)."""
    gate = asyncio.Event()

    async def handler() -> None:
        await gate.wait()

    runner = TaskRunner(clock)
    item = registered(interval_task(overlap=OverlapPolicy.SKIP), handler)
    first = asyncio.ensure_future(runner.run(item, scheduled_for=NOW))
    for _ in range(10):
        await asyncio.sleep(0)

    second = await runner.run(item, scheduled_for=NOW)
    gate.set()
    await first

    assert second.status is TaskExecutionStatus.SKIPPED


async def test_manual_run_during_scheduled_run_is_skipped(clock: FakeClock) -> None:
    """Ручной запуск подчиняется overlap policy (§32)."""
    gate = asyncio.Event()

    async def handler() -> None:
        await gate.wait()

    registry = TaskRegistry()
    item = registered(interval_task(), handler)
    registry.tasks[item.task.task_id] = item
    runner = TaskRunner(clock)
    scheduler = Scheduler(registry=registry, runner=runner, clock=clock)

    background = asyncio.ensure_future(scheduler.trigger(item.task.task_id))
    for _ in range(10):
        await asyncio.sleep(0)
    manual = await scheduler.trigger(item.task.task_id)
    gate.set()
    await background

    assert manual is not None
    assert manual.status is TaskExecutionStatus.SKIPPED


async def test_timeout_is_a_failure_not_a_retry(clock: FakeClock) -> None:
    """Истечение timeout не запускает бесконечный retry (§51)."""
    attempts: list[int] = []

    async def handler() -> None:
        attempts.append(1)
        await asyncio.sleep(10)

    runner = TaskRunner(clock)
    outcome = await runner.run(
        registered(interval_task(), handler, timeout=timedelta(seconds=0.01)),
        scheduled_for=NOW,
    )

    assert outcome.status is TaskExecutionStatus.FAILED
    assert outcome.execution.error_code == "task_timeout"
    assert attempts == [1]


async def test_task_failure_is_isolated(clock: FakeClock) -> None:
    """Сбой одной задачи не мешает другой (§43)."""

    async def failing() -> None:
        raise ProviderError("provider is down", provider_code="oneinch")

    healthy_calls: list[int] = []

    async def healthy() -> None:
        healthy_calls.append(1)

    registry = TaskRegistry()
    for task_id, handler in (("broken", failing), ("healthy", healthy)):
        item = registered(interval_task(task_id), handler)
        registry.tasks[task_id] = item
    scheduler = Scheduler(registry=registry, runner=TaskRunner(clock), clock=clock)
    await scheduler.prepare()

    outcomes = await scheduler.tick()

    statuses = {outcome.execution.task_id: outcome.status for outcome in outcomes}
    assert statuses["broken"] is TaskExecutionStatus.FAILED
    assert statuses["healthy"] is TaskExecutionStatus.SUCCESS
    assert healthy_calls == [1]


async def test_cancellation_stops_running_tasks(clock: FakeClock) -> None:
    """Shutdown отменяет выполняющиеся задачи (§49)."""
    started = asyncio.Event()

    async def handler() -> None:
        started.set()
        await asyncio.sleep(10)

    registry = TaskRegistry()
    item = registered(interval_task(), handler)
    registry.tasks[item.task.task_id] = item
    runner = TaskRunner(clock)
    scheduler = Scheduler(registry=registry, runner=runner, clock=clock)

    running = asyncio.ensure_future(scheduler.trigger(item.task.task_id))
    await asyncio.wait_for(started.wait(), timeout=5)
    await scheduler.shutdown()
    outcome = await running

    assert outcome is not None
    assert outcome.status is TaskExecutionStatus.CANCELLED
    assert runner.running_tasks == ()


# --- расписание и startup -------------------------------------------------


async def test_tick_runs_only_due_tasks(clock: FakeClock) -> None:
    calls: list[str] = []

    async def handler() -> None:
        calls.append("run")

    registry = TaskRegistry()
    item = registered(interval_task(seconds=300), handler)
    registry.tasks[item.task.task_id] = item
    scheduler = Scheduler(registry=registry, runner=TaskRunner(clock), clock=clock)
    await scheduler.prepare()

    assert len(await scheduler.tick()) == 1
    assert await scheduler.tick() == ()

    clock.advance(timedelta(seconds=301))
    assert len(await scheduler.tick()) == 1
    assert calls == ["run", "run"]


async def test_startup_tasks_follow_dependency_order(clock: FakeClock) -> None:
    """Resource Manager → Registries → Fee System → Scanner (§36)."""
    order: list[str] = []

    def make(name: str):  # noqa: ANN202 - локальная фабрика обработчиков
        async def handler() -> None:
            order.append(name)

        return handler

    registry = TaskRegistry()
    definitions = (
        ("scanner_startup", ("fee_startup",)),
        ("fee_startup", ("registry_startup",)),
        ("registry_startup", ("resources_startup",)),
        ("resources_startup", ()),
    )
    for task_id, depends_on in definitions:
        registry.tasks[task_id] = registered(
            SchedulerTask(task_id=task_id, mode=TaskMode.STARTUP),
            make(task_id),
            depends_on=depends_on,
        )
    scheduler = Scheduler(registry=registry, runner=TaskRunner(clock), clock=clock)

    await scheduler.run_startup()

    assert order == [
        "resources_startup",
        "registry_startup",
        "fee_startup",
        "scanner_startup",
    ]


async def test_startup_is_not_repeated(clock: FakeClock) -> None:
    """Повторный вызов не создаёт дублирующий startup."""
    calls: list[int] = []

    async def handler() -> None:
        calls.append(1)

    registry = TaskRegistry()
    registry.tasks["startup"] = registered(
        SchedulerTask(task_id="startup", mode=TaskMode.STARTUP), handler
    )
    scheduler = Scheduler(registry=registry, runner=TaskRunner(clock), clock=clock)

    await scheduler.run_startup()
    await scheduler.run_startup()

    assert calls == [1]


def test_dependency_cycle_is_rejected() -> None:
    """Циклическая зависимость — ошибка конфигурации."""

    async def handler() -> None:
        return None

    tasks = [
        registered(SchedulerTask(task_id="a", mode=TaskMode.STARTUP), handler, depends_on=("b",)),
        registered(SchedulerTask(task_id="b", mode=TaskMode.STARTUP), handler, depends_on=("a",)),
    ]
    with pytest.raises(ConfigurationError):
        startup_order(tasks)


# --- регистрация задач ----------------------------------------------------


def test_registry_uses_user_configuration() -> None:
    """Расписание берётся из конфигурации пользователя (§58-59)."""

    async def handler() -> None:
        return None

    config = SchedulerConfig(
        tasks={"level1_scan": TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=60)}
    )
    registry = TaskRegistry()
    item = registry.register(
        "level1_scan",
        handler,
        config=config,
        default=TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=300),
    )

    assert item.task.interval == timedelta(seconds=60)


def test_registry_falls_back_to_the_default_schedule() -> None:
    async def handler() -> None:
        return None

    registry = TaskRegistry()
    item = registry.register(
        "fee_refresh",
        handler,
        config=SchedulerConfig(),
        default=TaskScheduleConfig(mode=TaskMode.DAILY, time="04:00", timezone="Europe/Lisbon"),
    )

    assert item.task.mode is TaskMode.DAILY
    assert item.task.at_time == time(4, 0)
    assert item.task.timezone_name == "Europe/Lisbon"


def test_duplicate_registration_is_rejected() -> None:
    async def handler() -> None:
        return None

    registry = TaskRegistry()
    default = TaskScheduleConfig(mode=TaskMode.INTERVAL, interval_seconds=300)
    registry.register("task", handler, config=SchedulerConfig(), default=default)
    with pytest.raises(ConfigurationError):
        registry.register("task", handler, config=SchedulerConfig(), default=default)


# --- журнал запусков ------------------------------------------------------


class RecordingLog:
    """Персистентное расписание и журнал запусков в памяти."""

    def __init__(self, last: SchedulerExecution | None = None) -> None:
        self.records: list[SchedulerExecution] = []
        self.tasks: dict[str, SchedulerTaskState] = {}
        self._last = last

    async def upsert_task(self, state: SchedulerTaskState, *, updated_at: datetime) -> None:
        self.tasks[state.task_id] = state

    async def record_execution(self, execution: SchedulerExecution) -> None:
        self.records.append(execution)

    async def last_execution(self, task_id: str) -> SchedulerExecution | None:
        return self._last


async def test_executions_are_recorded(clock: FakeClock) -> None:
    async def handler() -> None:
        return None

    registry = TaskRegistry()
    item = registered(interval_task(), handler)
    registry.tasks[item.task.task_id] = item
    log = RecordingLog()
    scheduler = Scheduler(registry=registry, runner=TaskRunner(clock), clock=clock, log=log)
    await scheduler.prepare()

    await scheduler.tick()

    assert [record.status for record in log.records] == [TaskExecutionStatus.SUCCESS]
    # Задача сохранена до записи запуска: журнал ссылается на неё.
    assert "level1_scan" in log.tasks


async def test_schedule_resumes_from_the_last_successful_run(clock: FakeClock) -> None:
    """После рестарта расписание считается от последнего успеха (§35)."""

    async def handler() -> None:
        return None

    last = SchedulerExecution(
        execution_id="e1",
        task_id="level1_scan",
        status=TaskExecutionStatus.SUCCESS,
        scheduled_for=NOW - timedelta(seconds=100),
        started_at=NOW - timedelta(seconds=100),
        finished_at=NOW - timedelta(seconds=100),
    )
    registry = TaskRegistry()
    item = registered(interval_task(seconds=300), handler)
    registry.tasks[item.task.task_id] = item
    scheduler = Scheduler(
        registry=registry, runner=TaskRunner(clock), clock=clock, log=RecordingLog(last)
    )

    await scheduler.prepare()

    assert scheduler.next_run("level1_scan") == NOW + timedelta(seconds=200)
    assert await scheduler.tick() == ()
