"""Тесты уведомлений, комиссий, gas, capability, планировщика и журнала переходов."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.fees import FeeStatus
from monik.domain.enums.lifecycle import NotificationStatus, TaskExecutionStatus
from monik.domain.enums.notifications import DestinationKind, NotificationMode
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.scheduler import TaskMode
from monik.domain.errors import DatabaseError
from monik.domain.models.capability import Capability, CapabilityKey
from monik.domain.models.fee import FeeSnapshot
from monik.domain.models.notification import (
    Notification,
    NotificationAttempt,
    NotificationDestination,
)
from monik.domain.models.scan import Scan
from monik.domain.models.scheduler import SchedulerExecution
from monik.infrastructure.db import Database
from monik.repositories.sqlite import (
    SchedulerTaskState,
    SqliteCapabilityRepository,
    SqliteFeeRepository,
    SqliteGasRepository,
    SqliteNotificationRepository,
    SqliteOpportunityRepository,
    SqliteSchedulerRepository,
    SqliteStateTransitionRepository,
    StateTransitionRecord,
)
from tests import factories as f

OPPORTUNITY_ID = f.OpportunityId("44444444-4444-4444-8444-444444444444")


def _notification(
    notification_id: str = "n1",
    *,
    destination_id: str = "main-chat",
    sequence: int = 1,
    created_at: object = None,
) -> Notification:
    moment = created_at or f.NOW
    return Notification(
        notification_id=notification_id,
        opportunity_id=OPPORTUNITY_ID,
        destination=NotificationDestination(
            destination_id=destination_id,
            kind=DestinationKind.TELEGRAM,
            mode=NotificationMode.A,
        ),
        status=NotificationStatus.QUEUED,
        sequence=sequence,
        created_at=moment,  # type: ignore[arg-type]
        updated_at=moment,  # type: ignore[arg-type]
    )


@pytest.fixture
def notifications(database: Database) -> SqliteNotificationRepository:
    return SqliteNotificationRepository(database)


@pytest.fixture
def fees(database: Database) -> SqliteFeeRepository:
    return SqliteFeeRepository(database)


@pytest.fixture
def gas(database: Database) -> SqliteGasRepository:
    return SqliteGasRepository(database)


@pytest.fixture
def capabilities(database: Database) -> SqliteCapabilityRepository:
    return SqliteCapabilityRepository(database)


@pytest.fixture
def scheduler(database: Database) -> SqliteSchedulerRepository:
    return SqliteSchedulerRepository(database)


@pytest.fixture
def transitions(database: Database) -> SqliteStateTransitionRepository:
    return SqliteStateTransitionRepository(database)


@pytest.fixture
async def stored_opportunity(opportunities: SqliteOpportunityRepository, stored_scan: Scan) -> None:
    await opportunities.create_with_job(f.opportunity(), f.level2_job())


class TestNotificationRepository:
    async def test_create_and_get(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        notification = _notification()
        await notifications.create(notification)
        assert await notifications.get("n1") == notification

    async def test_logical_identity_is_unique(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        """Одна logical notification на destination (30 §41)."""
        await notifications.create(_notification("n1"))
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await notifications.create(_notification("n2"))

    async def test_find_logical(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        await notifications.create(_notification())
        found = await notifications.find_logical(OPPORTUNITY_ID, "main-chat")
        assert found is not None
        assert found.notification_id == "n1"
        assert await notifications.find_logical(OPPORTUNITY_ID, "other") is None

    async def test_multiple_destinations_are_allowed(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        """Одна Opportunity может иметь несколько уведомлений (36 §82)."""
        await notifications.create(_notification("n1", destination_id="chat-a"))
        await notifications.create(_notification("n2", destination_id="chat-b", sequence=2))
        assert len(await notifications.list_for_opportunity(OPPORTUNITY_ID)) == 2

    async def test_pending_are_ordered_by_creation_then_sequence(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        """Порядок отправки — created_at + sequence (CLAUDE.md §37)."""
        await notifications.create(
            _notification(
                "later", destination_id="c", sequence=1, created_at=f.NOW + timedelta(seconds=5)
            )
        )
        await notifications.create(_notification("first", destination_id="a", sequence=1))
        await notifications.create(_notification("second", destination_id="b", sequence=2))
        pending = await notifications.claim_pending(now=f.NOW + timedelta(minutes=1), limit=10)
        assert [item.notification_id for item in pending] == ["first", "second", "later"]

    async def test_retry_wait_is_not_claimed_before_time(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        await notifications.create(_notification())
        await notifications.update_delivery_state(
            "n1",
            NotificationStatus.RETRY_WAIT,
            updated_at=f.NOW,
            attempt_count=1,
            next_attempt_at=f.NOW + timedelta(minutes=5),
        )
        assert await notifications.claim_pending(now=f.NOW, limit=10) == ()
        later = await notifications.claim_pending(now=f.NOW + timedelta(minutes=6), limit=10)
        assert len(later) == 1

    async def test_sent_notification_is_not_claimed(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        """Доставленное уведомление не отправляется повторно (35 §81)."""
        await notifications.create(_notification())
        await notifications.update_delivery_state(
            "n1", NotificationStatus.SENT, updated_at=f.NOW, attempt_count=1
        )
        assert await notifications.claim_pending(now=f.NOW + timedelta(hours=1), limit=10) == ()

    async def test_attempts_are_recorded(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        await notifications.create(_notification())
        await notifications.record_attempt(
            "n1",
            NotificationAttempt(
                attempt_number=1,
                started_at=f.NOW,
                finished_at=f.NOW + timedelta(seconds=1),
                status=NotificationStatus.SENT,
                external_message_id="42",
            ),
        )
        attempts = await notifications.list_attempts("n1")
        assert len(attempts) == 1
        assert attempts[0].external_message_id == "42"

    async def test_duplicate_attempt_number_is_rejected(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        await notifications.create(_notification())
        attempt = NotificationAttempt(
            attempt_number=1, started_at=f.NOW, status=NotificationStatus.SENDING
        )
        await notifications.record_attempt("n1", attempt)
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await notifications.record_attempt("n1", attempt)

    async def test_texts_are_stored_for_details_button(
        self, notifications: SqliteNotificationRepository, stored_opportunity: None
    ) -> None:
        """Кнопка «об» использует сохранённый снимок (CLAUDE.md §35)."""
        await notifications.create(
            _notification(), message_text="short", details_text="full details"
        )
        assert await notifications.load_texts("n1") == ("short", "full details")


class TestFeeRepository:
    def _snapshot(self, *, snapshot_id: str = "fs1", with_unknown: bool = True) -> FeeSnapshot:
        fees = (f.known_fee(),) + ((f.unknown_fee(),) if with_unknown else ())
        return FeeSnapshot(
            snapshot_id=snapshot_id,
            provider_id=ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=OperationType.BUY,
            fees=fees,
            version=1,
            created_at=f.NOW,
        )

    async def test_round_trip(self, fees: SqliteFeeRepository) -> None:
        snapshot = self._snapshot()
        await fees.save(snapshot)
        loaded = await fees.get("fs1")
        assert loaded == snapshot

    async def test_unknown_fee_is_stored_without_amount(self, fees: SqliteFeeRepository) -> None:
        """UNKNOWN не превращается в ноль (07 §15)."""
        await fees.save(self._snapshot())
        loaded = await fees.get("fs1")
        assert loaded is not None
        unknown = [fee for fee in loaded.fees if fee.status is FeeStatus.UNKNOWN]
        assert len(unknown) == 1
        assert unknown[0].amount is None

    async def test_decimal_precision_is_preserved(self, fees: SqliteFeeRepository) -> None:
        snapshot = self._snapshot(with_unknown=False).replace(
            fees=(f.known_fee(amount="0.000000000000000001").model_dump(),)
        )
        await fees.save(snapshot)
        loaded = await fees.get("fs1")
        assert loaded is not None
        assert loaded.fees[0].known_amount == Decimal("0.000000000000000001")

    async def test_latest_returns_newest_snapshot(self, fees: SqliteFeeRepository) -> None:
        await fees.save(self._snapshot(snapshot_id="old"))
        await fees.save(
            self._snapshot(snapshot_id="new").replace(
                created_at=f.NOW + timedelta(hours=1), version=2
            )
        )
        latest = await fees.latest(ProviderId.ONEINCH, f.POLYGON, OperationType.BUY)
        assert latest is not None
        assert latest.snapshot_id == "new"

    async def test_latest_is_context_specific(self, fees: SqliteFeeRepository) -> None:
        """Fee key не обобщается чрезмерно (07 §46)."""
        await fees.save(self._snapshot())
        assert await fees.latest(ProviderId.ZERO_X, f.POLYGON, OperationType.BUY) is None
        assert await fees.latest(ProviderId.ONEINCH, f.POLYGON, OperationType.SELL) is None

    async def test_retention_removes_old_snapshots(self, fees: SqliteFeeRepository) -> None:
        await fees.save(self._snapshot())
        assert await fees.delete_created_before(f.NOW + timedelta(days=1)) == 1
        assert await fees.get("fs1") is None

    async def test_records_cascade_with_snapshot(
        self, fees: SqliteFeeRepository, database: Database
    ) -> None:
        await fees.save(self._snapshot())
        await fees.delete_created_before(f.NOW + timedelta(days=1))
        assert await database.fetch_all("SELECT record_id FROM fee_records") == []


class TestGasRepository:
    async def test_known_gas_round_trip(self, gas: SqliteGasRepository) -> None:
        await gas.save(f.known_gas())
        loaded = await gas.latest(f.POLYGON)
        assert loaded is not None
        assert loaded.is_known
        assert loaded.known_cost_native == Decimal("0.03")
        assert loaded.gas_price is not None
        assert loaded.gas_price.wei_per_gas == 120_000_000_000

    async def test_unknown_gas_has_no_cost(self, gas: SqliteGasRepository) -> None:
        """UNKNOWN gas не равен нулю (09 §16)."""
        await gas.save(f.unknown_gas())
        loaded = await gas.latest(f.POLYGON)
        assert loaded is not None
        assert not loaded.is_known
        assert loaded.cost_native is None

    async def test_latest_returns_newest(self, gas: SqliteGasRepository) -> None:
        await gas.save(f.known_gas(cost_native="0.03"))
        await gas.save(
            f.known_gas(cost_native="0.05").replace(observed_at=f.NOW + timedelta(minutes=1))
        )
        loaded = await gas.latest(f.POLYGON)
        assert loaded is not None
        assert loaded.known_cost_native == Decimal("0.05")

    async def test_retention(self, gas: SqliteGasRepository) -> None:
        await gas.save(f.known_gas())
        assert await gas.delete_observed_before(f.NOW + timedelta(days=1)) == 1
        assert await gas.latest(f.POLYGON) is None


class TestCapabilityRepository:
    def _capability(self, status: CapabilityStatus) -> Capability:
        return Capability(
            key=CapabilityKey(
                provider_id=ProviderId.ONEINCH,
                network_id=f.POLYGON,
                operation=CapabilityOperation.QUOTE_BUY,
            ),
            status=status,
            checked_at=f.NOW,
            expires_at=f.NOW + timedelta(days=1),
            source="discovery",
        )

    async def test_upsert_and_get(self, capabilities: SqliteCapabilityRepository) -> None:
        capability = self._capability(CapabilityStatus.SUPPORTED)
        await capabilities.upsert(capability)
        assert await capabilities.get(capability.key) == capability

    async def test_upsert_updates_existing(self, capabilities: SqliteCapabilityRepository) -> None:
        await capabilities.upsert(self._capability(CapabilityStatus.UNKNOWN))
        await capabilities.upsert(self._capability(CapabilityStatus.SUPPORTED))
        loaded = await capabilities.get(self._capability(CapabilityStatus.SUPPORTED).key)
        assert loaded is not None
        assert loaded.status is CapabilityStatus.SUPPORTED
        assert len(await capabilities.list_all()) == 1

    async def test_unknown_is_persisted_as_unknown(
        self, capabilities: SqliteCapabilityRepository
    ) -> None:
        """UNKNOWN не превращается в SUPPORTED при сохранении (36 §61)."""
        await capabilities.upsert(self._capability(CapabilityStatus.UNKNOWN))
        loaded = await capabilities.get(self._capability(CapabilityStatus.UNKNOWN).key)
        assert loaded is not None
        assert loaded.status is CapabilityStatus.UNKNOWN

    async def test_list_for_provider(self, capabilities: SqliteCapabilityRepository) -> None:
        await capabilities.upsert(self._capability(CapabilityStatus.SUPPORTED))
        assert len(await capabilities.list_for_provider(ProviderId.ONEINCH)) == 1
        assert await capabilities.list_for_provider(ProviderId.VELORA) == ()


class TestSchedulerRepository:
    def _state(self, *, next_run_at: object = None) -> SchedulerTaskState:
        return SchedulerTaskState(
            task_id="level1_scan",
            mode=TaskMode.INTERVAL,
            enabled=True,
            schedule={"interval_seconds": 300},
            next_run_at=next_run_at,  # type: ignore[arg-type]
        )

    async def test_upsert_and_get(self, scheduler: SqliteSchedulerRepository) -> None:
        await scheduler.upsert_task(self._state(), updated_at=f.NOW)
        loaded = await scheduler.get_task("level1_scan")
        assert loaded is not None
        assert loaded.mode is TaskMode.INTERVAL
        assert loaded.schedule == {"interval_seconds": 300}

    async def test_state_survives_reconnect(
        self, scheduler: SqliteSchedulerRepository, database: Database
    ) -> None:
        """Расписание восстанавливается после рестарта (30 §53)."""
        await scheduler.upsert_task(
            self._state(next_run_at=f.NOW + timedelta(minutes=5)), updated_at=f.NOW
        )
        await database.close()
        await database.connect()
        loaded = await SqliteSchedulerRepository(database).get_task("level1_scan")
        assert loaded is not None
        assert loaded.next_run_at == f.NOW + timedelta(minutes=5)

    async def test_list_enabled_skips_disabled(self, scheduler: SqliteSchedulerRepository) -> None:
        await scheduler.upsert_task(self._state(), updated_at=f.NOW)
        disabled = SchedulerTaskState(
            task_id="cleanup", mode=TaskMode.DAILY, enabled=False, schedule={}
        )
        await scheduler.upsert_task(disabled, updated_at=f.NOW)
        enabled = await scheduler.list_enabled()
        assert [task.task_id for task in enabled] == ["level1_scan"]

    async def test_executions_are_recorded(self, scheduler: SqliteSchedulerRepository) -> None:
        await scheduler.upsert_task(self._state(), updated_at=f.NOW)
        execution = SchedulerExecution(
            execution_id="e1",
            task_id="level1_scan",
            status=TaskExecutionStatus.SUCCESS,
            scheduled_for=f.NOW,
            started_at=f.NOW,
            finished_at=f.NOW + timedelta(seconds=10),
        )
        await scheduler.record_execution(execution)
        assert await scheduler.last_execution("level1_scan") == execution

    async def test_execution_requires_existing_task(
        self, scheduler: SqliteSchedulerRepository
    ) -> None:
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await scheduler.record_execution(
                SchedulerExecution(
                    execution_id="e1",
                    task_id="missing",
                    status=TaskExecutionStatus.SKIPPED,
                    scheduled_for=f.NOW,
                )
            )

    async def test_execution_retention(self, scheduler: SqliteSchedulerRepository) -> None:
        await scheduler.upsert_task(self._state(), updated_at=f.NOW)
        await scheduler.record_execution(
            SchedulerExecution(
                execution_id="e1",
                task_id="level1_scan",
                status=TaskExecutionStatus.SUCCESS,
                scheduled_for=f.NOW,
                started_at=f.NOW,
                finished_at=f.NOW,
            )
        )
        assert await scheduler.delete_executions_before(f.NOW + timedelta(days=1)) == 1
        assert await scheduler.last_execution("level1_scan") is None


class TestStateTransitionRepository:
    def _record(self, to_state: str, *, offset_seconds: int = 0) -> StateTransitionRecord:
        return StateTransitionRecord(
            entity_type="level2_job",
            entity_id="#K1234",
            from_state="queued" if to_state != "queued" else None,
            to_state=to_state,
            reason="test_transition",
            occurred_at=f.NOW + timedelta(seconds=offset_seconds),
            correlation_id="corr-1",
        )

    async def test_records_transition(self, transitions: SqliteStateTransitionRepository) -> None:
        await transitions.record(self._record("running"))
        history = await transitions.history("level2_job", "#K1234")
        assert len(history) == 1
        assert history[0].to_state == "running"
        assert history[0].reason == "test_transition"

    async def test_history_is_chronological(
        self, transitions: SqliteStateTransitionRepository
    ) -> None:
        await transitions.record(self._record("confirmed", offset_seconds=10))
        await transitions.record(self._record("running", offset_seconds=5))
        history = await transitions.history("level2_job", "#K1234")
        assert [item.to_state for item in history] == ["running", "confirmed"]

    async def test_history_is_scoped_to_entity(
        self, transitions: SqliteStateTransitionRepository
    ) -> None:
        await transitions.record(self._record("running"))
        assert await transitions.history("opportunity", "#V1234") == ()

    async def test_retention(self, transitions: SqliteStateTransitionRepository) -> None:
        await transitions.record(self._record("running"))
        assert await transitions.delete_before(f.NOW + timedelta(days=1)) == 1
        assert await transitions.history("level2_job", "#K1234") == ()
