"""Health Monitoring и Supervisor: пороги, гистерезис и безопасная остановка."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from monik.app.supervisor import SupervisedWorker, Supervisor
from monik.config.sections.health import HealthConfig
from monik.domain.enums.health import (
    ApplicationHealthStatus,
    ProviderHealthStatus,
    SupervisorState,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DatabaseError, ProviderError
from monik.services.health.monitor import HealthMonitor
from monik.services.observability import FakeClock

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def monitor(clock: FakeClock) -> HealthMonitor:
    return HealthMonitor(
        HealthConfig(
            provider_degraded_threshold=2,
            provider_failure_threshold=4,
            provider_recovery_threshold=2,
        ),
        clock,
    )


def healthy_core(monitor: HealthMonitor) -> None:
    """Перевести критические подсистемы в рабочее состояние."""
    for component in ("configuration", "database", "resource_manager", "scheduler"):
        monitor.set_component(component, ApplicationHealthStatus.HEALTHY)


# --- состояние провайдеров ------------------------------------------------


def test_unknown_provider_is_not_healthy(monitor: HealthMonitor) -> None:
    """``UNKNOWN`` не означает ``HEALTHY`` (``35`` §92)."""
    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.UNKNOWN


def test_single_failure_does_not_change_state(monitor: HealthMonitor) -> None:
    """Единичный сбой не переключает состояние (``19`` §49)."""
    monitor.record_provider_success(ProviderId.ONEINCH)
    monitor.record_provider_success(ProviderId.ONEINCH)
    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.HEALTHY

    monitor.record_provider_failure(ProviderId.ONEINCH, reason="timeout")

    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.HEALTHY


def test_degraded_threshold_is_applied(monitor: HealthMonitor) -> None:
    """Достижение порога деградации переводит в ``DEGRADED`` (``19`` §50)."""
    for _ in range(2):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="timeout")

    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.DEGRADED


def test_failure_threshold_marks_unavailable(monitor: HealthMonitor) -> None:
    for _ in range(4):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="500")

    health = monitor.provider(ProviderId.ONEINCH)
    assert health.status is ProviderHealthStatus.UNAVAILABLE
    assert health.consecutive_failures == 4


def test_recovery_requires_its_own_threshold(monitor: HealthMonitor) -> None:
    """Гистерезис: восстановление требует отдельного порога (``19`` §51-52)."""
    for _ in range(4):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="500")

    monitor.record_provider_success(ProviderId.ONEINCH)
    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.RECOVERING

    monitor.record_provider_success(ProviderId.ONEINCH)
    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.HEALTHY


def test_flapping_is_prevented(monitor: HealthMonitor) -> None:
    """Чередование одиночных сбоев и успехов не переключает состояние."""
    monitor.record_provider_success(ProviderId.ONEINCH)
    monitor.record_provider_success(ProviderId.ONEINCH)
    statuses = set()
    for _ in range(5):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="timeout")
        statuses.add(monitor.provider(ProviderId.ONEINCH).status)
        monitor.record_provider_success(ProviderId.ONEINCH)
        statuses.add(monitor.provider(ProviderId.ONEINCH).status)

    assert statuses == {ProviderHealthStatus.HEALTHY}


def test_providers_are_isolated(monitor: HealthMonitor) -> None:
    """Недоступность одного провайдера не влияет на другой (``19`` §12)."""
    for _ in range(4):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="500")
    monitor.record_provider_success(ProviderId.ZERO_X)
    monitor.record_provider_success(ProviderId.ZERO_X)

    assert monitor.provider(ProviderId.ONEINCH).status is ProviderHealthStatus.UNAVAILABLE
    assert monitor.provider(ProviderId.ZERO_X).status is ProviderHealthStatus.HEALTHY
    assert monitor.usable_providers() == (ProviderId.ZERO_X,)


# --- состояние приложения -------------------------------------------------


def test_one_unavailable_provider_degrades_but_does_not_stop(
    monitor: HealthMonitor,
) -> None:
    """Один недоступный провайдер не делает приложение недоступным (``19`` §12)."""
    healthy_core(monitor)
    for _ in range(4):
        monitor.record_provider_failure(ProviderId.ONEINCH, reason="500")
    monitor.record_provider_success(ProviderId.ZERO_X)
    monitor.record_provider_success(ProviderId.ZERO_X)

    assert monitor.application_health().status is ApplicationHealthStatus.DEGRADED


def test_all_providers_unavailable_is_degraded_by_policy(
    monitor: HealthMonitor,
) -> None:
    """Недоступность всех провайдеров отражается отдельно (``19`` §13)."""
    healthy_core(monitor)
    for provider in (ProviderId.ONEINCH, ProviderId.ZERO_X):
        for _ in range(4):
            monitor.record_provider_failure(provider, reason="500")

    assert monitor.application_health().status is ApplicationHealthStatus.DEGRADED


def test_unavailable_critical_component_makes_application_unavailable(
    monitor: HealthMonitor,
) -> None:
    """Критическая подсистема определяет общий статус (``19`` §9-10)."""
    healthy_core(monitor)
    monitor.set_component("database", ApplicationHealthStatus.UNAVAILABLE, reason="disk failure")

    assert monitor.application_health().status is ApplicationHealthStatus.UNAVAILABLE


def test_healthy_application_requires_healthy_core(monitor: HealthMonitor) -> None:
    healthy_core(monitor)
    monitor.record_provider_success(ProviderId.ONEINCH)
    monitor.record_provider_success(ProviderId.ONEINCH)

    assert monitor.application_health().status is ApplicationHealthStatus.HEALTHY


def test_starting_is_not_an_error(monitor: HealthMonitor) -> None:
    """``STARTING`` не считается ошибкой (``19`` §7)."""
    monitor.set_component("database", ApplicationHealthStatus.STARTING)

    assert monitor.application_health().status is ApplicationHealthStatus.STARTING


def test_stopping_is_reported(monitor: HealthMonitor) -> None:
    healthy_core(monitor)
    monitor.mark_stopping()

    assert monitor.application_health().status is ApplicationHealthStatus.STOPPING


def test_health_does_not_change_business_data(monitor: HealthMonitor) -> None:
    """Health только описывает состояние и ничего не меняет (``19`` §54-55)."""
    healthy_core(monitor)
    before = monitor.application_health()
    monitor.record_provider_failure(ProviderId.ONEINCH, reason="timeout")
    after = monitor.application_health()

    assert before.components == after.components
    assert all(hasattr(item, "status") for item in after.providers)


# --- Supervisor -----------------------------------------------------------


async def test_non_critical_worker_is_restarted(monitor: HealthMonitor, clock: FakeClock) -> None:
    """Упавший некритический worker восстанавливается (``CLAUDE.md`` §34)."""
    attempts: list[int] = []
    done = asyncio.Event()

    async def flaky() -> None:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise ProviderError("temporary failure", provider_code="oneinch")
        done.set()

    supervisor = Supervisor(monitor=monitor, clock=clock, config=HealthConfig())
    supervisor.register(SupervisedWorker(name="telegram", run=flaky))
    await supervisor.start()
    state = await supervisor.supervise()

    assert done.is_set()
    assert supervisor.restarts["telegram"] == 1
    assert state in {SupervisorState.DEGRADED, SupervisorState.STOPPED}


async def test_restart_limit_is_respected(monitor: HealthMonitor, clock: FakeClock) -> None:
    """Бесконечные перезапуски запрещены."""
    attempts: list[int] = []

    async def always_failing() -> None:
        attempts.append(1)
        raise ProviderError("down", provider_code="oneinch")

    supervisor = Supervisor(
        monitor=monitor, clock=clock, config=HealthConfig(worker_restart_limit=2)
    )
    supervisor.register(SupervisedWorker(name="maintenance", run=always_failing))
    await supervisor.start()
    await supervisor.supervise()

    assert len(attempts) == 3
    component = monitor.component("maintenance")
    assert component is not None
    assert component.status is ApplicationHealthStatus.UNAVAILABLE


async def test_database_failure_triggers_safe_stop(
    monitor: HealthMonitor, clock: FakeClock
) -> None:
    """Критическая ошибка persistence переводит в SAFE_STOP (``CLAUDE.md`` §34)."""
    stopped = asyncio.Event()

    async def broken_persistence() -> None:
        raise DatabaseError("integrity check failed")

    async def other_worker() -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            stopped.set()
            raise

    supervisor = Supervisor(monitor=monitor, clock=clock)
    supervisor.register(SupervisedWorker(name="level1", run=other_worker))
    supervisor.register(SupervisedWorker(name="database", run=broken_persistence))
    await supervisor.start()
    state = await supervisor.supervise()

    assert state is SupervisorState.SAFE_STOP
    assert stopped.is_set()
    assert supervisor.restarts.get("database") is None


async def test_critical_worker_failure_stops_the_system(
    monitor: HealthMonitor, clock: FakeClock
) -> None:
    """Падение критического worker'а не перезапускается вслепую."""

    async def failing() -> None:
        raise ProviderError("level 2 crashed", provider_code="internal")

    supervisor = Supervisor(monitor=monitor, clock=clock)
    supervisor.register(SupervisedWorker(name="level2", run=failing, critical=True))
    await supervisor.start()
    state = await supervisor.supervise()

    assert state is SupervisorState.SAFE_STOP
    assert supervisor.restarts.get("level2") is None


async def test_shutdown_cancels_workers(monitor: HealthMonitor, clock: FakeClock) -> None:
    """Graceful shutdown останавливает воркеры."""
    started = asyncio.Event()

    async def worker() -> None:
        started.set()
        await asyncio.sleep(30)

    supervisor = Supervisor(monitor=monitor, clock=clock)
    supervisor.register(SupervisedWorker(name="level1", run=worker))
    await supervisor.start()
    await asyncio.wait_for(started.wait(), timeout=5)
    await supervisor.shutdown()

    assert supervisor.state is SupervisorState.STOPPED
    assert monitor.application_health().status is ApplicationHealthStatus.STOPPING


def test_duplicate_worker_registration_is_rejected(
    monitor: HealthMonitor, clock: FakeClock
) -> None:
    async def worker() -> None:
        return None

    supervisor = Supervisor(monitor=monitor, clock=clock)
    supervisor.register(SupervisedWorker(name="level1", run=worker))
    with pytest.raises(ValueError, match="already registered"):
        supervisor.register(SupervisedWorker(name="level1", run=worker))
