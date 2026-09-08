"""Тесты Resource Manager."""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

import pytest

from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import (
    CircuitState,
    RequestPriority,
    ResourceResultStatus,
)
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    ProviderError,
    RateLimitError,
    ResourceError,
    TimeoutError,
)
from monik.domain.models.resource import ResourceKey
from monik.services.observability import FakeClock
from monik.services.resources import ResourceLimits, ResourceManager
from tests import factories as f

from .conftest import ControlledSleeper, request, resource_config

KEY = ResourceKey(provider_id=ProviderId.ONEINCH, network_id=f.POLYGON)


def _manager(
    clock: FakeClock,
    sleeper: ControlledSleeper,
    rng: random.Random,
    **config_overrides: object,
) -> ResourceManager:
    return ResourceManager(resource_config(**config_overrides), clock, sleeper=sleeper, rng=rng)


async def _ok(value: str = "ok") -> str:
    return value


class TestSuccessPath:
    async def test_executes_operation(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        assert await manager.execute(request(), lambda: _ok()) == "ok"

    async def test_records_metrics(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        await manager.execute(request(), lambda: _ok())
        results = manager.results()
        assert len(results) == 1
        assert results[0].status is ResourceResultStatus.SUCCESS
        assert results[0].attempts == 1
        assert results[0].total_latency >= timedelta(0)

    async def test_releases_slot_after_success(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        for _ in range(5):
            await manager.execute(request(), lambda: _ok())
        assert manager.queue_depth() == 0


class TestConcurrency:
    async def test_limits_parallel_execution(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=2)
        active = 0
        peak = 0
        release = asyncio.Event()

        async def operation() -> str:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await release.wait()
            active -= 1
            return "ok"

        tasks = [
            asyncio.create_task(manager.execute(request(sequence=index), operation))
            for index in range(5)
        ]
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(*tasks)
        assert peak <= 2

    async def test_independent_resources_run_in_parallel(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Операции на разных ресурсах не блокируют друг друга (CLAUDE.md §15)."""
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=4)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocking() -> str:
            started.set()
            await release.wait()
            return "blocked"

        blocked = asyncio.create_task(
            manager.execute(request(provider=ProviderId.ONEINCH), blocking)
        )
        await started.wait()
        assert (
            await manager.execute(request(provider=ProviderId.ZERO_X), lambda: _ok("other"))
            == "other"
        )
        release.set()
        assert await blocked == "blocked"

    async def test_queue_overflow_is_rejected(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Очередь не растёт бесконечно (12 §42-43)."""
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1, queue_capacity=1)
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "ok"

        first = asyncio.create_task(manager.execute(request(sequence=1), blocking))
        await asyncio.sleep(0)
        second = asyncio.create_task(manager.execute(request(sequence=2), blocking))
        await asyncio.sleep(0)
        with pytest.raises(ResourceError, match="queue .* is full"):
            await manager.execute(request(sequence=3), blocking)
        release.set()
        await asyncio.gather(first, second)

    async def test_wait_timeout_is_reported(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(
            clock,
            sleeper,
            rng,
            global_max_concurrent_requests=1,
            queue_wait_timeout_seconds=0.01,
        )
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "ok"

        first = asyncio.create_task(manager.execute(request(sequence=1), blocking))
        await asyncio.sleep(0)
        with pytest.raises(TimeoutError, match="waiting for"):
            await manager.execute(request(sequence=2), lambda: _ok())
        release.set()
        await first


class TestPriority:
    async def test_level2_is_served_before_level1(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Level 2 имеет приоритет над Level 1 (CLAUDE.md §15)."""
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        order: list[str] = []
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "blocking"

        def make(label: str) -> object:
            async def operation() -> str:
                order.append(label)
                return label

            return operation

        holder = asyncio.create_task(manager.execute(request(sequence=0), blocking))
        await asyncio.sleep(0)
        low = asyncio.create_task(
            manager.execute(
                request(priority=RequestPriority.LEVEL1_BUY, sequence=1),
                make("level1"),  # type: ignore[arg-type]
            )
        )
        await asyncio.sleep(0)
        high = asyncio.create_task(
            manager.execute(
                request(priority=RequestPriority.LEVEL2, sequence=2),
                make("level2"),  # type: ignore[arg-type]
            )
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(holder, low, high)
        assert order == ["level2", "level1"]

    async def test_ready_sell_outranks_pending_buy(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        order: list[str] = []
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "blocking"

        def make(label: str) -> object:
            async def operation() -> str:
                order.append(label)
                return label

            return operation

        holder = asyncio.create_task(manager.execute(request(sequence=0), blocking))
        await asyncio.sleep(0)
        buy = asyncio.create_task(
            manager.execute(
                request(priority=RequestPriority.LEVEL1_BUY, sequence=1),
                make("buy"),  # type: ignore[arg-type]
            )
        )
        await asyncio.sleep(0)
        sell = asyncio.create_task(
            manager.execute(
                request(priority=RequestPriority.LEVEL1_SELL, sequence=2),
                make("sell"),  # type: ignore[arg-type]
            )
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(holder, buy, sell)
        assert order == ["sell", "buy"]

    async def test_fifo_within_same_priority(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        order: list[int] = []
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "blocking"

        def make(index: int) -> object:
            async def operation() -> int:
                order.append(index)
                return index

            return operation

        holder = asyncio.create_task(manager.execute(request(sequence=0), blocking))
        await asyncio.sleep(0)
        tasks = []
        for index in (1, 2, 3):
            tasks.append(
                asyncio.create_task(
                    manager.execute(request(sequence=index), make(index))  # type: ignore[arg-type]
                )
            )
            await asyncio.sleep(0)
        release.set()
        await asyncio.gather(holder, *tasks)
        assert order == [1, 2, 3]


class TestRetry:
    async def test_retries_temporary_failure(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def flaky() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ProviderError("temporary upstream failure")
            return "ok"

        assert await manager.execute(request(), flaky) == "ok"
        assert attempts == 3
        assert manager.results()[-1].attempts == 3

    async def test_stops_after_budget(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def always_failing() -> str:
            nonlocal attempts
            attempts += 1
            raise ProviderError("still failing")

        with pytest.raises(ProviderError):
            await manager.execute(request(), always_failing)
        assert attempts == 3

    async def test_non_retryable_error_is_not_repeated(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Data error повтором не исправляется (CLAUDE.md §12)."""
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def malformed() -> str:
            nonlocal attempts
            attempts += 1
            raise DataError("malformed response")

        with pytest.raises(DataError):
            await manager.execute(request(), malformed)
        assert attempts == 1

    async def test_authentication_error_is_not_repeated(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def unauthorized() -> str:
            nonlocal attempts
            attempts += 1
            raise AuthenticationError("bad key")

        with pytest.raises(AuthenticationError):
            await manager.execute(request(), unauthorized)
        assert attempts == 1

    async def test_retry_after_is_honoured(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """HTTP 429 учитывает Retry-After (CLAUDE.md §32)."""
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def limited() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RateLimitError("slow down", retry_after=timedelta(seconds=7))
            return "ok"

        assert await manager.execute(request(), limited) == "ok"
        assert sleeper.delays[0] == 7.0

    async def test_backoff_grows(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)

        async def always_failing() -> str:
            raise ProviderError("boom")

        with pytest.raises(ProviderError):
            await manager.execute(request(), always_failing)
        assert sleeper.delays == [0.1, 0.2]

    async def test_timeout_is_normalized_and_retried(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        attempts = 0

        async def slow() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                await asyncio.sleep(10)
            return "ok"

        assert await manager.execute(request(timeout_seconds=0.01), slow) == "ok"
        assert attempts == 2


class TestCircuitBreakerIntegration:
    async def test_opens_after_repeated_failures(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)

        async def failing() -> str:
            raise ProviderError("down")

        with pytest.raises(ProviderError):
            await manager.execute(request(), failing)
        assert manager.circuit_state(KEY) is CircuitState.OPEN

    async def test_open_circuit_rejects_without_calling(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        called = 0

        async def failing() -> str:
            nonlocal called
            called += 1
            raise ProviderError("down")

        with pytest.raises(ProviderError):
            await manager.execute(request(), failing)
        before = called
        with pytest.raises(ResourceError, match="circuit breaker is open"):
            await manager.execute(request(), failing)
        assert called == before

    async def test_recovers_after_timeout(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)

        async def failing() -> str:
            raise ProviderError("down")

        with pytest.raises(ProviderError):
            await manager.execute(request(), failing)
        clock.advance(timedelta(seconds=11))
        assert await manager.execute(request(), lambda: _ok()) == "ok"
        assert manager.circuit_state(KEY) is CircuitState.CLOSED

    async def test_breaker_is_per_resource(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Сбой одного провайдера не останавливает остальные (01 §38)."""
        manager = _manager(clock, sleeper, rng)

        async def failing() -> str:
            raise ProviderError("down")

        with pytest.raises(ProviderError):
            await manager.execute(request(provider=ProviderId.ONEINCH), failing)
        assert (
            await manager.execute(request(provider=ProviderId.ZERO_X), lambda: _ok("fine"))
            == "fine"
        )


class TestDeduplication:
    async def test_identical_requests_are_merged(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Одинаковые одновременные запросы объединяются (12 §45)."""
        manager = _manager(clock, sleeper, rng)
        calls = 0
        release = asyncio.Event()

        async def operation() -> str:
            nonlocal calls
            calls += 1
            await release.wait()
            return "shared"

        tasks = [
            asyncio.create_task(
                manager.execute(request(deduplication_key="fees:oneinch"), operation)
            )
            for _ in range(4)
        ]
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*tasks)
        assert results == ["shared"] * 4
        assert calls == 1
        assert manager.merged_requests == 3

    async def test_different_keys_are_not_merged(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            return "value"

        await manager.execute(request(deduplication_key="a"), operation)
        await manager.execute(request(deduplication_key="b"), operation)
        assert calls == 2
        assert manager.merged_requests == 0

    async def test_merged_consumers_share_the_error(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        release = asyncio.Event()

        async def failing() -> str:
            await release.wait()
            raise DataError("bad payload")

        tasks = [
            asyncio.create_task(manager.execute(request(deduplication_key="same"), failing))
            for _ in range(3)
        ]
        await asyncio.sleep(0)
        release.set()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(item, DataError) for item in outcomes)


class TestRateLimiting:
    async def test_waits_for_rate_limit(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng)
        manager.register_limits(
            KEY, ResourceLimits(max_concurrent=4, requests_per_second=2.0, burst=1)
        )
        for _ in range(3):
            await manager.execute(request(), lambda: _ok())
        assert sleeper.total_slept > 0

    async def test_batch_costs_more_than_one_unit(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Batch не считается одним запросом автоматически (05 §56)."""
        manager = _manager(clock, sleeper, rng)
        manager.register_limits(
            KEY, ResourceLimits(max_concurrent=4, requests_per_second=1.0, burst=5)
        )
        await manager.execute(request(batch_units=5), lambda: _ok())
        assert sleeper.total_slept == 0
        await manager.execute(request(batch_units=5), lambda: _ok())
        assert sleeper.total_slept > 0

    async def test_rate_limit_is_separate_from_concurrency(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Rate limit и concurrency — разные ограничения (12 §19)."""
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=8)
        manager.register_limits(
            KEY, ResourceLimits(max_concurrent=8, requests_per_second=1.0, burst=1)
        )
        await manager.execute(request(), lambda: _ok())
        await manager.execute(request(), lambda: _ok())
        assert sleeper.total_slept >= 1.0


class TestCancellation:
    async def test_cancellation_releases_slot(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        """Отмена не оставляет удерживаемых разрешений (12 §41)."""
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        started = asyncio.Event()

        async def never_ends() -> str:
            started.set()
            await asyncio.sleep(3600)
            return "never"

        task = asyncio.create_task(manager.execute(request(), never_ends))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await manager.execute(request(), lambda: _ok()) == "ok"

    async def test_cancelled_waiter_does_not_block_queue(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=1)
        release = asyncio.Event()

        async def blocking() -> str:
            await release.wait()
            return "blocking"

        holder = asyncio.create_task(manager.execute(request(sequence=0), blocking))
        await asyncio.sleep(0)
        waiting = asyncio.create_task(manager.execute(request(sequence=1), lambda: _ok()))
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        release.set()
        await holder
        assert await manager.execute(request(sequence=2), lambda: _ok("after")) == "after"


class TestHierarchicalLimits:
    async def test_operation_scope_limits_apply(
        self, clock: FakeClock, sleeper: ControlledSleeper, rng: random.Random
    ) -> None:
        manager = _manager(clock, sleeper, rng, global_max_concurrent_requests=8)
        narrow = ResourceKey(
            provider_id=ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=CapabilityOperation.QUOTE_BUY,
        )
        manager.register_limits(
            narrow, ResourceLimits(max_concurrent=1, requests_per_second=100.0, burst=100)
        )
        active = 0
        peak = 0
        release = asyncio.Event()

        async def operation() -> str:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await release.wait()
            active -= 1
            return "ok"

        tasks = [
            asyncio.create_task(
                manager.execute(
                    request(sequence=index, operation=CapabilityOperation.QUOTE_BUY),
                    operation,
                )
            )
            for index in range(3)
        ]
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(*tasks)
        assert peak == 1
