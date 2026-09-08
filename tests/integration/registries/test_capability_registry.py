"""Тесты Capability Registry."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest

from monik.config.sections.capabilities import CapabilityConfig
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.errors import ErrorCategory
from monik.domain.enums.providers import ProviderId
from monik.domain.models.capability import CapabilityKey
from monik.infrastructure.db import Database, MigrationRunner
from monik.repositories.sqlite import SqliteCapabilityRepository
from monik.services.observability import FakeClock
from monik.services.registries import CapabilityRegistry
from tests import factories as f

KEY = CapabilityKey(
    provider_id=ProviderId.ONEINCH,
    network_id=f.POLYGON,
    operation=CapabilityOperation.QUOTE_BUY,
)
OTHER_KEY = CapabilityKey(
    provider_id=ProviderId.ZERO_X,
    network_id=f.POLYGON,
    operation=CapabilityOperation.FIXED_ROUTE,
)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "caps.db")))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def repository(database: Database) -> SqliteCapabilityRepository:
    return SqliteCapabilityRepository(database)


@pytest.fixture
def registry(repository: SqliteCapabilityRepository, clock: FakeClock) -> CapabilityRegistry:
    return CapabilityRegistry(repository, CapabilityConfig(failure_threshold=3), clock)


class TestUnknownIsNotSupported:
    def test_missing_capability_is_unknown(self, registry: CapabilityRegistry) -> None:
        """UNKNOWN не эквивалентен SUPPORTED (36 §61)."""
        assert registry.status(KEY) is CapabilityStatus.UNKNOWN
        assert not registry.is_confirmed(KEY)

    def test_unknown_allows_runtime_check(self, registry: CapabilityRegistry) -> None:
        """UNKNOWN не означает UNSUPPORTED (10 §16)."""
        assert registry.allows_request(KEY)

    async def test_unsupported_blocks_request(self, registry: CapabilityRegistry) -> None:
        """Явно неподдерживаемые комбинации не запрашиваются (02 §76)."""
        await registry.record_discovery(KEY, CapabilityStatus.UNSUPPORTED, source="discovery")
        assert not registry.allows_request(KEY)
        assert not registry.is_confirmed(KEY)


class TestDiscovery:
    async def test_records_supported(self, registry: CapabilityRegistry) -> None:
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        assert registry.is_confirmed(KEY)
        assert registry.allows_request(KEY)

    async def test_persists_across_reload(
        self,
        registry: CapabilityRegistry,
        repository: SqliteCapabilityRepository,
        clock: FakeClock,
    ) -> None:
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        fresh = CapabilityRegistry(repository, CapabilityConfig(), clock)
        assert await fresh.load() == 1
        assert fresh.is_confirmed(KEY)

    async def test_stale_after_freshness_window(
        self, registry: CapabilityRegistry, clock: FakeClock
    ) -> None:
        """Просроченная capability не считается актуальной (30 §51)."""
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        clock.advance(timedelta(days=2))
        assert registry.status(KEY) is CapabilityStatus.STALE
        assert not registry.is_confirmed(KEY)
        assert registry.allows_request(KEY)

    async def test_stale_keys_are_reported_for_refresh(
        self, registry: CapabilityRegistry, clock: FakeClock
    ) -> None:
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        assert registry.stale_keys() == ()
        clock.advance(timedelta(days=2))
        assert [str(key) for key in registry.stale_keys()] == [str(KEY)]


class TestRuntimeSignals:
    async def test_temporary_error_does_not_mark_unsupported(
        self, registry: CapabilityRegistry
    ) -> None:
        """Timeout и 5xx не переводят capability в UNSUPPORTED (06 §77)."""
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        for _ in range(10):
            await registry.record_failure(KEY, ErrorCategory.TIMEOUT)
        assert registry.status(KEY) is not CapabilityStatus.UNSUPPORTED
        assert registry.allows_request(KEY)

    async def test_rate_limit_does_not_change_state(self, registry: CapabilityRegistry) -> None:
        """RATE_LIMITED — временное ограничение, не UNSUPPORTED (06 §76)."""
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        await registry.record_failure(KEY, ErrorCategory.RATE_LIMIT)
        assert registry.is_confirmed(KEY)

    async def test_resource_rejection_does_not_change_state(
        self, registry: CapabilityRegistry
    ) -> None:
        """Circuit breaker и очередь не изменяют реестр (05 §11)."""
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        await registry.record_failure(KEY, ErrorCategory.RESOURCE)
        assert registry.is_confirmed(KEY)

    async def test_single_unsupported_signal_is_not_enough(
        self, registry: CapabilityRegistry
    ) -> None:
        """Мгновенный permanent disable запрещён (20 §26)."""
        await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        assert registry.status(KEY) is not CapabilityStatus.UNSUPPORTED

    async def test_repeated_unsupported_signals_reach_threshold(
        self, registry: CapabilityRegistry
    ) -> None:
        for _ in range(3):
            await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        assert registry.status(KEY) is CapabilityStatus.UNSUPPORTED
        assert not registry.allows_request(KEY)

    async def test_success_resets_failure_counter(self, registry: CapabilityRegistry) -> None:
        await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        await registry.record_success(KEY)
        await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        assert registry.status(KEY) is not CapabilityStatus.UNSUPPORTED
        assert registry.get(KEY).consecutive_failures == 1

    async def test_success_confirms_support(self, registry: CapabilityRegistry) -> None:
        await registry.record_success(KEY)
        assert registry.is_confirmed(KEY)

    async def test_degraded_after_transient_failure(self, registry: CapabilityRegistry) -> None:
        await registry.record_discovery(KEY, CapabilityStatus.SUPPORTED, source="startup")
        await registry.record_failure(KEY, ErrorCategory.PROVIDER)
        assert registry.status(KEY) is CapabilityStatus.DEGRADED
        assert registry.allows_request(KEY)


class TestIsolation:
    async def test_keys_are_independent(self, registry: CapabilityRegistry) -> None:
        for _ in range(3):
            await registry.record_failure(KEY, ErrorCategory.UNSUPPORTED)
        assert registry.status(KEY) is CapabilityStatus.UNSUPPORTED
        assert registry.status(OTHER_KEY) is CapabilityStatus.UNKNOWN

    async def test_snapshot_lists_known_capabilities(self, registry: CapabilityRegistry) -> None:
        await registry.record_success(KEY)
        await registry.record_success(OTHER_KEY)
        assert len(registry.snapshot()) == 2

    def test_lookup_makes_no_io(self, registry: CapabilityRegistry) -> None:
        """Статический запрос не выполняет сетевых и дисковых вызовов (20 §79)."""
        assert registry.status(KEY) is CapabilityStatus.UNKNOWN
        assert registry.key(ProviderId.ONEINCH, f.POLYGON, CapabilityOperation.QUOTE_BUY) == KEY
