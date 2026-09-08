"""Тесты операционных моделей: notification, scan, capability, resource, scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from monik.domain.enums import (
    CapabilityOperation,
    CapabilityStatus,
    DestinationKind,
    NotificationStatus,
    OverlapPolicy,
    ProviderId,
    RequestPriority,
    ResourceResultStatus,
    ScanStatus,
    TaskExecutionStatus,
    TaskMode,
)
from monik.domain.models import (
    Capability,
    CapabilityKey,
    Notification,
    NotificationDestination,
    ResourceKey,
    ResourceRequest,
    ResourceResult,
    Scan,
    ScanScope,
    SchedulerExecution,
    SchedulerTask,
)
from monik.domain.value_objects import OpportunityId, RequestId
from tests import factories as f

_OPPORTUNITY_ID = OpportunityId("44444444-4444-4444-8444-444444444444")


def _notification(**overrides: object) -> Notification:
    base: dict[str, object] = {
        "notification_id": "n1",
        "opportunity_id": _OPPORTUNITY_ID,
        "destination": NotificationDestination(
            destination_id="main-chat", kind=DestinationKind.TELEGRAM
        ),
        "status": NotificationStatus.QUEUED,
        "sequence": 1,
        "created_at": f.NOW,
        "updated_at": f.NOW,
    }
    base.update(overrides)
    return Notification(**base)  # type: ignore[arg-type]


class TestNotification:
    def test_ordering_is_by_creation_then_sequence(self) -> None:
        """Порядок — created_at + sequence, не profit (CLAUDE.md §37)."""
        first = _notification(sequence=1)
        second = _notification(notification_id="n2", sequence=2)
        later = _notification(
            notification_id="n3",
            sequence=1,
            created_at=f.NOW + timedelta(seconds=1),
            updated_at=f.NOW + timedelta(seconds=1),
        )
        ordered = sorted([later, second, first], key=lambda n: n.ordering_key)
        assert [n.notification_id for n in ordered] == ["n1", "n2", "n3"]

    def test_fingerprint_is_opportunity_plus_destination(self) -> None:
        same = _notification(notification_id="other", sequence=7)
        assert same.fingerprint == _notification().fingerprint

    def test_fingerprint_differs_per_destination(self) -> None:
        other = _notification(
            destination=NotificationDestination(
                destination_id="second-chat", kind=DestinationKind.TELEGRAM
            )
        )
        assert other.fingerprint != _notification().fingerprint

    def test_retry_wait_requires_next_attempt_time(self) -> None:
        with pytest.raises(ValidationError, match="next_attempt_at"):
            _notification(status=NotificationStatus.RETRY_WAIT)

    def test_terminal_states(self) -> None:
        assert _notification(status=NotificationStatus.SENT).is_terminal
        assert not _notification(status=NotificationStatus.SENDING).is_terminal


class TestScan:
    def _scope(self) -> ScanScope:
        return ScanScope(
            networks=(f.POLYGON,),
            providers=(ProviderId.ONEINCH, ProviderId.ZERO_X),
            tokens=(f.AAVE.key,),
            raw_amounts=(100_000_000, 500_000_000),
        )

    def test_running_scan_has_no_finish_time(self) -> None:
        scan = Scan(
            scan_id=f.ScanId("33333333-3333-4333-8333-333333333333"),
            status=ScanStatus.RUNNING,
            scope=self._scope(),
            started_at=f.NOW,
        )
        assert scan.finished_at is None

    def test_completed_scan_requires_finish_time(self) -> None:
        with pytest.raises(ValidationError, match="must have finished_at"):
            Scan(
                scan_id=f.ScanId("33333333-3333-4333-8333-333333333333"),
                status=ScanStatus.COMPLETE,
                scope=self._scope(),
                started_at=f.NOW,
            )

    def test_partial_is_a_distinct_status(self) -> None:
        """PARTIAL не считается полностью успешным (02 §54)."""
        scan = Scan(
            scan_id=f.ScanId("33333333-3333-4333-8333-333333333333"),
            status=ScanStatus.PARTIAL,
            scope=self._scope(),
            started_at=f.NOW,
            finished_at=f.NOW + timedelta(seconds=30),
        )
        assert scan.status is not ScanStatus.COMPLETE

    def test_scope_rejects_non_positive_amounts(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            ScanScope(
                networks=(f.POLYGON,),
                providers=(ProviderId.ONEINCH,),
                tokens=(f.AAVE.key,),
                raw_amounts=(0,),
            )


class TestCapability:
    def _capability(self, status: CapabilityStatus, **overrides: object) -> Capability:
        base: dict[str, object] = {
            "key": CapabilityKey(
                provider_id=ProviderId.ONEINCH,
                network_id=f.POLYGON,
                operation=CapabilityOperation.QUOTE_BUY,
            ),
            "status": status,
            "checked_at": f.NOW,
            "expires_at": f.NOW + timedelta(days=1),
            "source": "discovery",
        }
        base.update(overrides)
        return Capability(**base)  # type: ignore[arg-type]

    def test_unknown_is_not_supported(self) -> None:
        """UNKNOWN никогда не равен SUPPORTED (36 §61)."""
        unknown = self._capability(CapabilityStatus.UNKNOWN)
        assert unknown.status is not CapabilityStatus.SUPPORTED
        assert not unknown.allows_request(f.NOW, allow_unknown=False)
        assert unknown.allows_request(f.NOW, allow_unknown=True)

    def test_unsupported_blocks_request_even_when_unknown_allowed(self) -> None:
        """Явно неподдерживаемые комбинации не запрашиваются (02 §76)."""
        unsupported = self._capability(CapabilityStatus.UNSUPPORTED)
        assert not unsupported.allows_request(f.NOW, allow_unknown=True)

    def test_supported_allows_request_while_fresh(self) -> None:
        supported = self._capability(CapabilityStatus.SUPPORTED)
        assert supported.allows_request(f.NOW, allow_unknown=False)

    def test_stale_supported_is_not_automatically_fresh(self) -> None:
        """Просроченная capability не считается актуальной (30 §51)."""
        supported = self._capability(CapabilityStatus.SUPPORTED)
        later = f.NOW + timedelta(days=2)
        assert not supported.is_fresh(later)
        assert not supported.allows_request(later, allow_unknown=False)

    def test_key_string_is_stable(self) -> None:
        key = CapabilityKey(
            provider_id=ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=CapabilityOperation.FIXED_ROUTE,
        )
        assert str(key) == "oneinch/polygon/fixed_route/*"


class TestResource:
    def _request(self, priority: RequestPriority, sequence: int = 0) -> ResourceRequest:
        return ResourceRequest(
            request_id=RequestId.generate(),
            key=ResourceKey(provider_id=ProviderId.ONEINCH, network_id=f.POLYGON),
            priority=priority,
            timeout=timedelta(seconds=10),
            created_at=f.NOW,
            sequence=sequence,
        )

    def test_level2_outranks_level1(self) -> None:
        """Level 2 обслуживается раньше Level 1 (CLAUDE.md §15)."""
        level2 = self._request(RequestPriority.LEVEL2, sequence=99)
        level1 = self._request(RequestPriority.LEVEL1_BUY, sequence=0)
        assert level2.ordering_key < level1.ordering_key

    def test_ready_sell_outranks_pending_buy(self) -> None:
        """Готовая SELL-проверка важнее незавершённой BUY (CLAUDE.md §15)."""
        sell = self._request(RequestPriority.LEVEL1_SELL, sequence=99)
        buy = self._request(RequestPriority.LEVEL1_BUY, sequence=0)
        assert sell.ordering_key < buy.ordering_key

    def test_maintenance_has_lower_priority(self) -> None:
        maintenance = self._request(RequestPriority.MAINTENANCE, sequence=0)
        level1 = self._request(RequestPriority.LEVEL1_BUY, sequence=99)
        assert level1.ordering_key < maintenance.ordering_key

    def test_fifo_within_same_priority(self) -> None:
        """Внутри приоритета — порядок постановки (05 §17)."""
        first = self._request(RequestPriority.LEVEL1_BUY, sequence=1)
        second = self._request(RequestPriority.LEVEL1_BUY, sequence=2)
        assert first.ordering_key < second.ordering_key

    def test_rejects_non_positive_timeout(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            ResourceRequest(
                request_id=RequestId.generate(),
                key=ResourceKey(provider_id=ProviderId.ONEINCH),
                priority=RequestPriority.LEVEL2,
                timeout=timedelta(0),
                created_at=f.NOW,
                sequence=0,
            )

    def test_hierarchical_keys(self) -> None:
        key = ResourceKey(
            provider_id=ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=CapabilityOperation.QUOTE_BUY,
        )
        assert str(key) == "oneinch/polygon/quote_buy"
        assert [str(parent) for parent in key.parents()] == ["oneinch", "oneinch/polygon"]

    def test_result_distinguishes_rate_limit_from_failure(self) -> None:
        """Rate limit не является обычной ошибкой (11 §55)."""
        result = ResourceResult(
            request_id=RequestId.generate(),
            status=ResourceResultStatus.RATE_LIMITED,
            queued_for=timedelta(seconds=1),
            executed_for=timedelta(seconds=2),
            finished_at=f.NOW,
            retry_after=timedelta(seconds=30),
        )
        assert result.status is not ResourceResultStatus.FAILURE
        assert result.total_latency == timedelta(seconds=3)


class TestSchedulerTask:
    def test_interval_task_requires_interval(self) -> None:
        with pytest.raises(ValidationError, match="positive interval"):
            SchedulerTask(task_id="level1", mode=TaskMode.INTERVAL)

    def test_daily_task_requires_time_and_timezone(self) -> None:
        with pytest.raises(ValidationError, match="at_time"):
            SchedulerTask(task_id="fees", mode=TaskMode.DAILY)
        with pytest.raises(ValidationError, match="timezone"):
            SchedulerTask(task_id="fees", mode=TaskMode.DAILY, at_time=time(2, 0))

    def test_startup_task_rejects_interval(self) -> None:
        with pytest.raises(ValidationError, match="not applicable"):
            SchedulerTask(task_id="startup", mode=TaskMode.STARTUP, interval=timedelta(minutes=5))

    def test_valid_daily_task(self) -> None:
        task = SchedulerTask(
            task_id="fee_refresh",
            mode=TaskMode.DAILY,
            at_time=time(2, 0),
            timezone_name="Europe/Lisbon",
            interval_days=1,
        )
        assert task.overlap_policy is OverlapPolicy.SKIP

    def test_valid_interval_task(self) -> None:
        task = SchedulerTask(
            task_id="level1_scan",
            mode=TaskMode.INTERVAL,
            interval=timedelta(minutes=5),
            priority=RequestPriority.LEVEL1_BUY,
        )
        assert task.interval == timedelta(minutes=5)


class TestSchedulerExecution:
    def test_cannot_finish_without_start(self) -> None:
        with pytest.raises(ValidationError, match="without having started"):
            SchedulerExecution(
                execution_id="e1",
                task_id="t1",
                status=TaskExecutionStatus.SUCCESS,
                scheduled_for=f.NOW,
                finished_at=f.NOW,
            )

    def test_skipped_execution_needs_no_times(self) -> None:
        execution = SchedulerExecution(
            execution_id="e1",
            task_id="t1",
            status=TaskExecutionStatus.SKIPPED,
            scheduled_for=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert execution.started_at is None
