"""Тесты хранилища Opportunity и её Level 2 Job."""

from __future__ import annotations

from datetime import timedelta

import pytest

from monik.domain.enums.lifecycle import JobStatus, OpportunityStatus
from monik.domain.errors import DatabaseError
from monik.domain.models.opportunity import Opportunity
from monik.domain.models.scan import Scan
from monik.repositories.sqlite import SqliteJobRepository, SqliteOpportunityRepository
from tests import factories as f


def _opportunity(**overrides: object) -> Opportunity:
    return f.opportunity(**overrides)  # type: ignore[arg-type]


class TestAtomicCreation:
    async def test_creates_opportunity_with_job(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        opportunity = _opportunity()
        job = f.level2_job()
        await opportunities.create_with_job(opportunity, job)
        assert await opportunities.get(opportunity.opportunity_id) is not None
        assert await jobs.get(job.k_id) is not None

    async def test_round_trip_preserves_model(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        opportunity = _opportunity(
            amounts=(
                f.opportunity_amount(input_raw=100_000_000),
                f.opportunity_amount(input_raw=500_000_000),
            )
        )
        await opportunities.create_with_job(opportunity, f.level2_job())
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded == opportunity

    async def test_preserves_route_snapshot_and_fingerprint(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        """Level 2 должен получить именно зафиксированный маршрут (11 §5)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded is not None
        assert loaded.routes.buy_route.fingerprint == opportunity.routes.buy_route.fingerprint
        assert loaded.routes.sell_route.fingerprint == opportunity.routes.sell_route.fingerprint
        assert loaded.fingerprint == opportunity.fingerprint

    async def test_preserves_decimal_precision(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded is not None
        original = opportunity.amounts[0].preliminary_result
        restored = loaded.amounts[0].preliminary_result
        assert restored.net_profit == original.net_profit
        assert restored.net_roi == original.net_roi

    async def test_preserves_intermediate_token_decimals(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        """Decimals промежуточного токена отличаются от входного (01 §10)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded is not None
        assert loaded.amounts[0].preliminary_buy_output.decimals == 18
        assert loaded.amounts[0].input_amount.decimals == 6

    async def test_rejects_job_of_another_opportunity(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        foreign_job = f.level2_job().replace(opportunity_id="55555555-5555-4555-8555-555555555555")
        with pytest.raises(DatabaseError, match="does not belong"):
            await opportunities.create_with_job(_opportunity(), foreign_job)

    async def test_failed_job_insert_rolls_back_opportunity(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        """Opportunity без её Job существовать не должна (CLAUDE.md §29)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        duplicate = _opportunity().replace(
            opportunity_id="66666666-6666-4666-8666-666666666666", v_id="#V4321"
        )
        with pytest.raises(DatabaseError):
            await opportunities.create_with_job(
                duplicate,
                f.level2_job().replace(opportunity_id="66666666-6666-4666-8666-666666666666"),
            )
        assert await opportunities.get(duplicate.opportunity_id) is None

    async def test_second_job_for_same_opportunity_is_rejected(
        self,
        opportunities: SqliteOpportunityRepository,
        stored_scan: Scan,
    ) -> None:
        """Дублирующий Level 2 workflow не создаётся (CLAUDE.md §19)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await opportunities.create_with_job(opportunity, f.level2_job().replace(k_id="#K9999"))


class TestLookups:
    async def test_get_by_v_id(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        loaded = await opportunities.get_by_v_id(opportunity.v_id)
        assert loaded is not None
        assert loaded.opportunity_id == opportunity.opportunity_id

    async def test_missing_returns_none(self, opportunities: SqliteOpportunityRepository) -> None:
        assert await opportunities.get_by_v_id(f.VId.from_sequence(999)) is None

    async def test_deduplication_by_fingerprint(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        """Одинаковая возможность находится по отпечатку (10 §52-53)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        found = await opportunities.find_recent_by_fingerprint(
            opportunity.fingerprint, since=f.NOW - timedelta(minutes=5)
        )
        assert found is not None
        assert found.opportunity_id == opportunity.opportunity_id

    async def test_deduplication_window_is_respected(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        assert (
            await opportunities.find_recent_by_fingerprint(
                opportunity.fingerprint, since=f.NOW + timedelta(minutes=1)
            )
            is None
        )

    async def test_list_by_status(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        await opportunities.create_with_job(_opportunity(), f.level2_job())
        created = await opportunities.list_by_status(OpportunityStatus.CREATED, limit=10)
        assert len(created) == 1
        assert await opportunities.list_by_status(OpportunityStatus.CONFIRMED, limit=10) == ()

    async def test_list_expired_only_returns_active(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        expired = await opportunities.list_expired(now=f.NOW + timedelta(minutes=10), limit=10)
        assert len(expired) == 1

        await opportunities.update_status(
            opportunity.opportunity_id,
            OpportunityStatus.CONFIRMED,
            updated_at=f.NOW,
            confirmed_at=f.NOW,
        )
        assert await opportunities.list_expired(now=f.NOW + timedelta(minutes=10), limit=10) == ()


class TestStatusUpdates:
    async def test_update_status_preserves_financial_snapshot(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        """Смена статуса не изменяет финансовые значения (35 §66)."""
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        await opportunities.update_status(
            opportunity.opportunity_id,
            OpportunityStatus.CONFIRMED,
            updated_at=f.NOW + timedelta(seconds=10),
            confirmed_at=f.NOW + timedelta(seconds=10),
        )
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded is not None
        assert loaded.status is OpportunityStatus.CONFIRMED
        assert loaded.amounts == opportunity.amounts
        assert loaded.routes == opportunity.routes

    async def test_notification_status_transition(
        self, opportunities: SqliteOpportunityRepository, stored_scan: Scan
    ) -> None:
        opportunity = _opportunity()
        await opportunities.create_with_job(opportunity, f.level2_job())
        for status in (OpportunityStatus.CONFIRMED, OpportunityStatus.NOTIFIED):
            await opportunities.update_status(opportunity.opportunity_id, status, updated_at=f.NOW)
        loaded = await opportunities.get(opportunity.opportunity_id)
        assert loaded is not None
        assert loaded.status is OpportunityStatus.NOTIFIED


class TestJobRepository:
    async def test_get_by_opportunity(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        opportunity = _opportunity()
        job = f.level2_job()
        await opportunities.create_with_job(opportunity, job)
        loaded = await jobs.get_by_opportunity(opportunity.opportunity_id)
        assert loaded is not None
        assert loaded.k_id == job.k_id

    async def test_claim_queued_skips_expired(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        await opportunities.create_with_job(_opportunity(), f.level2_job())
        assert len(await jobs.claim_queued(limit=10, now=f.NOW)) == 1
        assert await jobs.claim_queued(limit=10, now=f.NOW + timedelta(minutes=10)) == ()

    async def test_update_status_and_attempts(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        job = f.level2_job()
        await opportunities.create_with_job(_opportunity(), job)
        await jobs.update_status(job.k_id, JobStatus.RUNNING, updated_at=f.NOW, attempt_count=1)
        loaded = await jobs.get(job.k_id)
        assert loaded is not None
        assert loaded.status is JobStatus.RUNNING
        assert loaded.attempt_count == 1

    async def test_interrupted_jobs_are_discoverable(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        """RUNNING после краха не считается успехом (35 §135)."""
        job = f.level2_job()
        await opportunities.create_with_job(_opportunity(), job)
        await jobs.update_status(job.k_id, JobStatus.RUNNING, updated_at=f.NOW)
        interrupted = await jobs.list_interrupted()
        assert [item.k_id for item in interrupted] == [job.k_id]

    async def test_expired_jobs_are_discoverable(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        job = f.level2_job()
        await opportunities.create_with_job(_opportunity(), job)
        expired = await jobs.list_expired(now=f.NOW + timedelta(minutes=10), limit=10)
        assert [item.k_id for item in expired] == [job.k_id]

    async def test_terminal_jobs_are_not_expired(
        self,
        opportunities: SqliteOpportunityRepository,
        jobs: SqliteJobRepository,
        stored_scan: Scan,
    ) -> None:
        job = f.level2_job()
        await opportunities.create_with_job(_opportunity(), job)
        await jobs.update_status(job.k_id, JobStatus.CONFIRMED, updated_at=f.NOW)
        assert await jobs.list_expired(now=f.NOW + timedelta(minutes=10), limit=10) == ()
