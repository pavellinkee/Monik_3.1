"""Тесты сохранения результатов Level 2."""

from __future__ import annotations

from datetime import timedelta

import pytest

from monik.domain.enums.lifecycle import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
)
from monik.domain.errors import DatabaseError
from monik.domain.models.job import (
    AmountVerificationResult,
    ConfirmationResult,
    Level2Attempt,
)
from monik.domain.models.scan import Scan
from monik.repositories.sqlite import SqliteJobRepository, SqliteOpportunityRepository
from tests import factories as f


def _verified_result(
    *, profitable: bool = True, input_raw: int = 100_000_000
) -> AmountVerificationResult:
    candidate = f.candidate()
    return AmountVerificationResult(
        input_amount=f.USDT.amount_from_base_units(input_raw),
        status=(
            AmountVerificationStatus.VERIFIED_PROFITABLE
            if profitable
            else AmountVerificationStatus.VERIFIED_UNPROFITABLE
        ),
        buy_quote=candidate.buy_quote,
        sell_quote=candidate.sell_quote,
        current_buy_output=candidate.buy_quote.output_amount,
        current_sell_output=candidate.sell_quote.output_amount,
        gas=f.known_gas(),
        profit_result=f.profit_result(net_roi="1.50" if profitable else "0.50", passed=profitable),
    )


def _unverified_result(status: AmountVerificationStatus) -> AmountVerificationResult:
    return AmountVerificationResult(
        input_amount=f.USDT.amount_from_base_units(500_000_000),
        status=status,
        rejection_reason="route could not be reproduced",
    )


def _confirmation(*results: AmountVerificationResult, revision: int = 1) -> ConfirmationResult:
    return ConfirmationResult(
        k_id=f.KId.from_sequence(1234),
        opportunity_id=f.OpportunityId("44444444-4444-4444-8444-444444444444"),
        revision=revision,
        job_status=JobStatus.CONFIRMED,
        amount_results=results,
        completed_at=f.NOW + timedelta(seconds=20),
    )


@pytest.fixture
async def prepared(opportunities: SqliteOpportunityRepository, stored_scan: Scan) -> None:
    await opportunities.create_with_job(f.opportunity(), f.level2_job())


class TestConfirmationPersistence:
    async def test_round_trip_verified_result(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        confirmation = _confirmation(_verified_result())
        await jobs.save_confirmation(confirmation)
        loaded = await jobs.load_confirmation(confirmation.k_id, 1)
        assert loaded is not None
        assert loaded.confirmed_count == 1
        result = loaded.amount_results[0]
        assert result.status is AmountVerificationStatus.VERIFIED_PROFITABLE
        assert result.profit_result is not None
        assert result.profit_result.net_roi == _verified_result().profit_result.net_roi  # type: ignore[union-attr]

    async def test_stores_quotes_for_verified_results(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        """Котировки — подтверждение принятого решения (11 §66-67)."""
        await jobs.save_confirmation(_confirmation(_verified_result()))
        loaded = await jobs.load_confirmation(f.KId.from_sequence(1234), 1)
        assert loaded is not None
        result = loaded.amount_results[0]
        assert result.buy_quote is not None
        assert result.sell_quote is not None

    async def test_does_not_store_quotes_for_unverified_results(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        """Полный поток Level 2 quotes не сохраняется (11 §69)."""
        await jobs.save_confirmation(
            _confirmation(_unverified_result(AmountVerificationStatus.ROUTE_UNAVAILABLE))
        )
        loaded = await jobs.load_confirmation(f.KId.from_sequence(1234), 1)
        assert loaded is not None
        result = loaded.amount_results[0]
        assert result.buy_quote is None
        assert result.rejection_reason == "route could not be reproduced"

    async def test_mixed_results_keep_separate_statuses(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        """Каждая сумма получает собственный статус (11 §46)."""
        await jobs.save_confirmation(
            _confirmation(
                _verified_result(profitable=True, input_raw=100_000_000),
                _verified_result(profitable=False, input_raw=200_000_000),
                _unverified_result(AmountVerificationStatus.UNKNOWN),
            )
        )
        loaded = await jobs.load_confirmation(f.KId.from_sequence(1234), 1)
        assert loaded is not None
        assert loaded.confirmed_count == 1
        assert loaded.unconfirmed_count == 1
        assert loaded.partial_count == 1
        statuses = {result.confirmation_status for result in loaded.amount_results}
        assert statuses == {
            AmountConfirmationStatus.CONFIRMED,
            AmountConfirmationStatus.UNCONFIRMED,
            AmountConfirmationStatus.PARTIAL,
        }

    async def test_gas_snapshot_is_preserved(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        await jobs.save_confirmation(_confirmation(_verified_result()))
        loaded = await jobs.load_confirmation(f.KId.from_sequence(1234), 1)
        assert loaded is not None
        gas = loaded.amount_results[0].gas
        assert gas is not None
        assert gas.known_cost_native == f.known_gas().known_cost_native

    async def test_revisions_are_independent(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        """Повторная проверка создаёт новую ревизию, а не новый Job (04 §24)."""
        await jobs.save_confirmation(_confirmation(_verified_result(), revision=1))
        await jobs.save_confirmation(_confirmation(_verified_result(profitable=False), revision=2))
        first = await jobs.load_confirmation(f.KId.from_sequence(1234), 1)
        second = await jobs.load_confirmation(f.KId.from_sequence(1234), 2)
        assert first is not None and second is not None
        assert first.confirmed_count == 1
        assert second.unconfirmed_count == 1

    async def test_duplicate_revision_is_rejected(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        await jobs.save_confirmation(_confirmation(_verified_result()))
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await jobs.save_confirmation(_confirmation(_verified_result()))

    async def test_missing_confirmation_returns_none(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        assert await jobs.load_confirmation(f.KId.from_sequence(1234), 7) is None

    async def test_failed_save_leaves_nothing_behind(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        """Частично записанный результат проверки недопустим."""
        broken = _confirmation(_verified_result()).replace(k_id="#K7777")
        with pytest.raises(DatabaseError):
            await jobs.save_confirmation(broken)
        assert await jobs.load_confirmation(f.KId.from_sequence(7777), 1) is None


class TestAttempts:
    async def test_records_attempt(self, jobs: SqliteJobRepository, prepared: None) -> None:
        attempt = Level2Attempt(
            revision=1,
            started_at=f.NOW,
            finished_at=f.NOW + timedelta(seconds=5),
            status=JobStatus.CONFIRMED,
        )
        attempt_id = await jobs.record_attempt(attempt, k_id=f.KId.from_sequence(1234))
        assert attempt_id

    async def test_duplicate_revision_is_rejected(
        self, jobs: SqliteJobRepository, prepared: None
    ) -> None:
        attempt = Level2Attempt(revision=1, started_at=f.NOW, status=JobStatus.RUNNING)
        await jobs.record_attempt(attempt, k_id=f.KId.from_sequence(1234))
        with pytest.raises(DatabaseError, match="integrity constraint"):
            await jobs.record_attempt(attempt, k_id=f.KId.from_sequence(1234))
