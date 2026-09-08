"""Opportunity Service: подтверждение, снимок и постановка доставки."""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from pydantic import ValidationError

from monik.config import Configuration, parse_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.lifecycle import (
    AmountVerificationStatus,
    NotificationStatus,
    OpportunityStatus,
)
from monik.domain.enums.notifications import DestinationKind, NotificationMode
from monik.domain.models.confirmation import ConfirmationSnapshot
from monik.domain.models.job import ConfirmationResult
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.db import Database, MigrationRunner
from monik.repositories.sqlite import (
    SqliteConfirmationRepository,
    SqliteIdSequenceRepository,
    SqliteNotificationRepository,
    SqliteOpportunityRepository,
)
from monik.services.observability import FakeClock
from monik.services.opportunity import (
    ConfirmationStatistics,
    DeliveryOutcome,
    OpportunityService,
    build_snapshot,
    delivery_status_for,
)
from tests import factories as f
from tests.component.level1.conftest import level1_document
from tests.component.level2.conftest import build_level2
from tests.unit.config.conftest import VALID_ENV

TELEGRAM = NotificationDestination(
    destination_id="chat-main", kind=DestinationKind.TELEGRAM, mode=NotificationMode.A
)
SECOND = NotificationDestination(
    destination_id="chat-backup", kind=DestinationKind.TELEGRAM, mode=NotificationMode.B
)


def configured(**scanner_overrides: object) -> Configuration:
    return parse_configuration(level1_document(**scanner_overrides), environ=dict(VALID_ENV)).config


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(
        DatabaseConfig(path=str(tmp_path / "opportunity.db"), busy_timeout_seconds=1.0)
    )
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


class RecordingRenderer:
    """Формирует тексты из снимка и считает вызовы."""

    def __init__(self) -> None:
        self.calls: list[ConfirmationSnapshot] = []

    def render(self, snapshot: ConfirmationSnapshot) -> tuple[str, str]:
        self.calls.append(snapshot)
        return (f"{snapshot.k_id} confirmed", f"{snapshot.k_id} details")


def build_service(
    database: Database,
    clock: FakeClock,
    *,
    destinations: tuple[NotificationDestination, ...] = (TELEGRAM,),
    renderer: RecordingRenderer | None = None,
) -> OpportunityService:
    return OpportunityService(
        publisher=SqliteConfirmationRepository(database),
        notifications=SqliteNotificationRepository(database),
        opportunities=SqliteOpportunityRepository(database),
        sequences=SqliteIdSequenceRepository(database),
        clock=clock,
        destinations=destinations,
        renderer=renderer,
    )


async def confirmed_case(
    database: Database, clock: FakeClock, **overrides: object
) -> tuple[object, ConfirmationResult]:
    """Подтверждённая Level 2 возможность."""
    harness = await build_level2(configured(**overrides), database, clock)
    result = await harness.scanner.confirm(harness.job)
    return harness.opportunity, result


# --- фиксация подтверждения ----------------------------------------------


async def test_confirmed_opportunity_is_recorded_and_queued(
    database: Database, clock: FakeClock
) -> None:
    """CONFIRMED фиксируется, доставка ставится в очередь (§7)."""
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock, renderer=RecordingRenderer())

    outcome = await service.record_confirmation(opportunity, result)

    assert outcome.status is OpportunityStatus.CONFIRMED
    assert outcome.is_notifiable
    assert len(outcome.notifications) == 1
    assert outcome.notifications[0].status is NotificationStatus.QUEUED


async def test_opportunity_is_persisted_before_delivery(
    database: Database, clock: FakeClock
) -> None:
    """Возможность сохранена до начала доставки (§4).

    Уведомление существует только в состоянии ``QUEUED``: доставка ещё не
    начиналась, а статус возможности уже записан.
    """
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock, renderer=RecordingRenderer())

    await service.record_confirmation(opportunity, result)

    stored = await SqliteOpportunityRepository(database).get(opportunity.opportunity_id)
    queued = await SqliteNotificationRepository(database).list_for_opportunity(
        opportunity.opportunity_id
    )
    assert stored is not None and stored.status is OpportunityStatus.CONFIRMED
    assert [item.status for item in queued] == [NotificationStatus.QUEUED]


async def test_unconfirmed_result_is_never_queued(database: Database, clock: FakeClock) -> None:
    """Неподтверждённая возможность пользователю не отправляется (§7)."""
    opportunity, result = await confirmed_case(database, clock)
    rejected = result.replace(
        amount_results=tuple(
            item.replace(
                status=AmountVerificationStatus.VERIFIED_UNPROFITABLE,
                profit_result=f.profit_result(passed=False),
            )
            for item in result.amount_results
        )
    )
    service = build_service(database, clock, renderer=RecordingRenderer())

    outcome = await service.record_confirmation(opportunity, rejected)

    assert outcome.status is OpportunityStatus.UNPROFITABLE
    assert outcome.notifications == ()
    stored = await SqliteNotificationRepository(database).list_for_opportunity(
        opportunity.opportunity_id
    )
    assert stored == ()


async def test_repeated_event_does_not_duplicate_notifications(
    database: Database, clock: FakeClock
) -> None:
    """Повторная доставка события не создаёт дубли (``03`` §57-58)."""
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock, renderer=RecordingRenderer())

    first = await service.record_confirmation(opportunity, result)
    second = await service.record_confirmation(opportunity, result)

    assert second.already_recorded is True
    assert len(second.notifications) == len(first.notifications) == 1
    stored = await SqliteNotificationRepository(database).list_for_opportunity(
        opportunity.opportunity_id
    )
    assert len(stored) == 1


async def test_notifications_carry_stored_texts_for_the_details_button(
    database: Database, clock: FakeClock
) -> None:
    """Тексты сохраняются вместе с уведомлением (``CLAUDE.md`` §35)."""
    opportunity, result = await confirmed_case(database, clock)
    renderer = RecordingRenderer()
    service = build_service(database, clock, renderer=renderer)

    outcome = await service.record_confirmation(opportunity, result)

    repository = SqliteNotificationRepository(database)
    message, details = await repository.load_texts(outcome.notifications[0].notification_id)
    assert message == f"{result.k_id} confirmed"
    assert details == f"{result.k_id} details"
    assert len(renderer.calls) == 1


async def test_notification_order_follows_creation_sequence(
    database: Database, clock: FakeClock
) -> None:
    """Порядок задаётся ``created_at`` и sequence (``CLAUDE.md`` §37)."""
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock, destinations=(TELEGRAM, SECOND))

    outcome = await service.record_confirmation(opportunity, result)

    sequences = [item.sequence for item in outcome.notifications]
    assert sequences == sorted(sequences)
    assert [item.destination.destination_id for item in outcome.notifications] == [
        TELEGRAM.destination_id,
        SECOND.destination_id,
    ]


# --- снимок ---------------------------------------------------------------


async def test_snapshot_contains_confirmation_data(database: Database, clock: FakeClock) -> None:
    """Снимок содержит всё, что требуется уведомлению (§8)."""
    opportunity, result = await confirmed_case(database, clock)
    snapshot = build_snapshot(opportunity, result)

    assert snapshot.v_id == opportunity.v_id
    assert snapshot.k_id == result.k_id
    assert snapshot.routes == opportunity.routes
    assert snapshot.network_id == opportunity.network_id
    assert snapshot.formula_version == 1
    amount = snapshot.amounts[0]
    assert amount.buy_output is not None and amount.sell_output is not None
    assert amount.net_profit is not None and amount.net_roi is not None
    assert amount.gas is not None
    assert amount.fee_snapshots
    assert amount.threshold == Decimal("1.00")
    assert amount.threshold_passed is True
    assert snapshot.has_confirmed_amount is True


async def test_snapshot_is_immutable(database: Database, clock: FakeClock) -> None:
    """Обычное изменение финансового снимка запрещено (``35`` §66-67)."""
    opportunity, result = await confirmed_case(database, clock)
    snapshot = build_snapshot(opportunity, result)

    with pytest.raises(ValidationError):
        snapshot.amounts[0].net_profit = Decimal(999)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        snapshot.routes = opportunity.routes  # type: ignore[misc]


async def test_snapshot_rejects_a_foreign_result(database: Database, clock: FakeClock) -> None:
    opportunity, result = await confirmed_case(database, clock)
    foreign = result.replace(opportunity_id=f.OpportunityId.generate())

    with pytest.raises(ValueError, match="different opportunity"):
        build_snapshot(opportunity, foreign)


async def test_snapshot_does_not_recalculate(database: Database, clock: FakeClock) -> None:
    """Значения переносятся как есть (§14)."""
    opportunity, result = await confirmed_case(database, clock)
    snapshot = build_snapshot(opportunity, result)

    source = result.amount_results[0].profit_result
    assert source is not None
    assert snapshot.amounts[0].net_profit == source.net_profit
    assert snapshot.amounts[0].net_roi == source.net_roi
    assert snapshot.amounts[0].costs == source.costs


# --- notification-статусы -------------------------------------------------


async def test_full_delivery_marks_notified(database: Database, clock: FakeClock) -> None:
    """CONFIRMED → NOTIFIED после успешной доставки (``35`` §62)."""
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock)
    await service.record_confirmation(opportunity, result)

    status = await service.record_delivery(
        opportunity.opportunity_id, (DeliveryOutcome(TELEGRAM.destination_id, True),)
    )

    assert status is OpportunityStatus.NOTIFIED
    stored = await SqliteOpportunityRepository(database).get(opportunity.opportunity_id)
    assert stored is not None and stored.status is OpportunityStatus.NOTIFIED


def test_delivery_status_mapping() -> None:
    """Частичная доставка отражается отдельным статусом (``35`` §63-64)."""
    assert (
        delivery_status_for(
            (DeliveryOutcome("a", True), DeliveryOutcome("b", False)),
        )
        is OpportunityStatus.NOTIFIED_PARTIAL
    )
    assert delivery_status_for((DeliveryOutcome("a", False),)) is OpportunityStatus.NOTIFIED_FAILED
    assert delivery_status_for(()) is OpportunityStatus.NOTIFIED_FAILED


async def test_delivery_transition_keeps_the_financial_snapshot(
    database: Database, clock: FakeClock
) -> None:
    """Переход статуса ничего не пересчитывает (``35`` §65)."""
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock)
    await service.record_confirmation(opportunity, result)
    before = await SqliteOpportunityRepository(database).get(opportunity.opportunity_id)

    await service.record_delivery(
        opportunity.opportunity_id, (DeliveryOutcome(TELEGRAM.destination_id, True),)
    )
    after = await SqliteOpportunityRepository(database).get(opportunity.opportunity_id)

    assert before is not None and after is not None
    assert after.amounts == before.amounts
    assert after.routes == before.routes


# --- статистика -----------------------------------------------------------


async def test_confirmation_statistics_are_accumulated(
    database: Database, clock: FakeClock
) -> None:
    opportunity, result = await confirmed_case(database, clock)
    service = build_service(database, clock)

    await service.record_confirmation(opportunity, result)

    assert service.statistics.confirmed == 1
    assert service.statistics.unconfirmed == 0
    assert service.statistics.confirmation_rate == Decimal(100)


def test_confirmation_rate_excludes_partial() -> None:
    """``PARTIAL`` исключается из confirmation rate (``CLAUDE.md`` §27)."""
    statistics = ConfirmationStatistics(confirmed=1, unconfirmed=1, partial=5)
    assert statistics.confirmation_rate == Decimal(50)


def test_confirmation_rate_is_not_available_without_decisions() -> None:
    """Без CONFIRMED и UNCONFIRMED значение — ``N/A``."""
    assert ConfirmationStatistics(partial=3).confirmation_rate is None
