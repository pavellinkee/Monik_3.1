"""Тесты Opportunity, Candidate и Level 2 Job.

Проверяются ключевые архитектурные правила: единый маршрут на все суммы,
SELL от текущего BUY output, детерминированная дедупликация, разделение
CONFIRMED / UNCONFIRMED / PARTIAL.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from monik.domain.enums import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
    OperationType,
    OpportunityStatus,
    ProviderId,
    RoutingMode,
)
from monik.domain.models import (
    AmountVerificationResult,
    Candidate,
    ConfirmationResult,
    Opportunity,
    RouteSnapshot,
)
from tests import factories as f


class TestCandidate:
    def test_valid_round_trip(self) -> None:
        candidate = f.candidate()
        assert candidate.route_snapshot.input_token == f.USDT.key
        assert candidate.route_snapshot.intermediate_token == f.AAVE.key
        assert candidate.route_snapshot.output_token == f.USDT.key

    def test_sell_must_start_from_buy_intermediate_token(self) -> None:
        """BUY output token обязан совпадать с SELL input token (10 §82)."""
        candidate = f.candidate()
        wrong_sell = f.quote(
            operation=OperationType.SELL,
            input_token=f.WMATIC,
            output_token=f.USDT,
            input_raw=1,
            output_raw=1,
        )
        with pytest.raises(ValidationError, match="intermediate token"):
            candidate.replace(sell_quote=wrong_sell.model_dump())

    def test_sell_amount_must_equal_buy_output(self) -> None:
        candidate = f.candidate()
        with pytest.raises(ValidationError, match="input amount must equal"):
            candidate.replace(
                sell_quote={
                    **candidate.sell_quote.model_dump(),
                    "input_amount": f.AAVE.amount_from_base_units(1).model_dump(),
                }
            )

    def test_rejects_wrong_operation(self) -> None:
        candidate = f.candidate()
        with pytest.raises(ValidationError):
            candidate.replace(buy_quote=candidate.sell_quote.model_dump())

    def test_converts_to_amount_context(self) -> None:
        context = f.candidate().to_amount_context()
        assert context.input_amount == f.USDT.amount_from_base_units(100_000_000)


class TestRouteSnapshot:
    def test_rejects_non_round_trip(self) -> None:
        with pytest.raises(ValidationError, match="end at the input token"):
            RouteSnapshot(
                buy_route=f.route(operation=OperationType.BUY),
                sell_route=f.route(
                    operation=OperationType.SELL,
                    input_token=f.AAVE.key,
                    output_token=f.WMATIC.key,
                ),
            )

    def test_rejects_wrong_operations(self) -> None:
        with pytest.raises(ValidationError, match="BUY operation"):
            RouteSnapshot(
                buy_route=f.route(operation=OperationType.SELL),
                sell_route=f.route(operation=OperationType.SELL),
            )


class TestOpportunity:
    def test_fingerprint_is_deterministic(self) -> None:
        assert f.opportunity().fingerprint == f.opportunity().fingerprint

    def test_fingerprint_ignores_random_identifier(self) -> None:
        """Дедупликация не должна зависеть от случайного ID (04 §23)."""
        base = f.opportunity()
        other = base.replace(v_id="#V9999", opportunity_id="55555555-5555-4555-8555-555555555555")
        assert base.fingerprint == other.fingerprint

    def test_fingerprint_depends_on_provider_pair(self) -> None:
        base = f.opportunity()
        assert base.buy_provider_id is ProviderId.ONEINCH
        changed = base.replace(
            buy_provider_id=ProviderId.VELORA.value,
            routes={
                "buy_route": f.route(
                    provider_id=ProviderId.VELORA, operation=OperationType.BUY
                ).model_dump(),
                "sell_route": base.routes.sell_route.model_dump(),
            },
        )
        assert changed.fingerprint != base.fingerprint

    def test_fingerprint_depends_on_route(self) -> None:
        base = f.opportunity()
        changed_route = f.route(
            provider_id=ProviderId.ONEINCH,
            operation=OperationType.BUY,
            routing_mode=RoutingMode.UNISWAP_V3,
        )
        changed = base.replace(
            routes={
                "buy_route": changed_route.model_dump(),
                "sell_route": base.routes.sell_route.model_dump(),
            }
        )
        assert changed.fingerprint != base.fingerprint

    def test_all_amounts_share_one_route(self) -> None:
        """Разные суммы не могут иметь разные маршруты (10 §24, §89)."""
        opportunity = f.opportunity(
            amounts=(
                f.opportunity_amount(input_raw=100_000_000),
                f.opportunity_amount(input_raw=500_000_000),
            )
        )
        assert len(opportunity.amounts) == 2
        assert opportunity.routes.buy_route.fingerprint == (
            opportunity.routes.buy_route.fingerprint
        )

    def test_rejects_duplicate_amounts(self) -> None:
        with pytest.raises(ValidationError, match="duplicate input amounts"):
            f.opportunity(
                amounts=(
                    f.opportunity_amount(input_raw=100_000_000),
                    f.opportunity_amount(input_raw=100_000_000),
                )
            )

    def test_requires_at_least_one_amount(self) -> None:
        with pytest.raises(ValidationError):
            f.opportunity(amounts=())

    def test_rejects_provider_mismatch_with_route(self) -> None:
        with pytest.raises(ValidationError, match="buy route provider"):
            f.opportunity().replace(buy_provider_id=ProviderId.UNISWAP.value)

    def test_expiration(self) -> None:
        opportunity = f.opportunity(lifetime=timedelta(minutes=5))
        assert not opportunity.is_expired(f.NOW + timedelta(minutes=4))
        assert opportunity.is_expired(f.NOW + timedelta(minutes=5))
        assert opportunity.time_to_expiry(f.NOW) == timedelta(minutes=5)

    def test_rejects_expiry_before_detection(self) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            f.opportunity(lifetime=timedelta(0))

    def test_amount_lookup(self) -> None:
        opportunity = f.opportunity(
            amounts=(
                f.opportunity_amount(input_raw=100_000_000),
                f.opportunity_amount(input_raw=500_000_000),
            )
        )
        assert opportunity.amount_for(500_000_000).input_amount.raw == 500_000_000
        with pytest.raises(KeyError):
            opportunity.amount_for(1)

    def test_is_immutable(self) -> None:
        opportunity = f.opportunity()
        with pytest.raises(ValidationError):
            opportunity.status = OpportunityStatus.CONFIRMED  # type: ignore[misc]

    def test_created_status_is_not_confirmation(self) -> None:
        """Level 1 не подтверждает возможность (10 §3)."""
        assert f.opportunity().status is OpportunityStatus.CREATED


class TestAmountVerificationResult:
    def _verified(self, **overrides: object) -> AmountVerificationResult:
        candidate = f.candidate()
        base: dict[str, object] = {
            "input_amount": f.USDT.amount_from_base_units(100_000_000),
            "status": AmountVerificationStatus.VERIFIED_PROFITABLE,
            "buy_quote": candidate.buy_quote,
            "sell_quote": candidate.sell_quote,
            "current_buy_output": candidate.buy_quote.output_amount,
            "current_sell_output": candidate.sell_quote.output_amount,
            "profit_result": f.profit_result(),
        }
        base.update(overrides)
        return AmountVerificationResult(**base)  # type: ignore[arg-type]

    def test_verified_result_requires_fresh_data(self) -> None:
        with pytest.raises(ValidationError, match="missing"):
            self._verified(buy_quote=None)

    def test_sell_must_use_current_buy_output(self) -> None:
        """SELL считается от текущего BUY output, не от Level 1 (11 §16-17)."""
        with pytest.raises(ValidationError, match="current buy output"):
            self._verified(current_buy_output=f.AAVE.amount_from_base_units(1))

    def test_profitable_requires_passing_calculation(self) -> None:
        with pytest.raises(ValidationError, match="VERIFIED_PROFITABLE"):
            self._verified(profit_result=f.profit_result(net_roi="0.5", passed=False))

    def test_confirmation_mapping(self) -> None:
        """PARTIAL не смешивается с CONFIRMED (CLAUDE.md §26)."""
        assert self._verified().confirmation_status is AmountConfirmationStatus.CONFIRMED
        unprofitable = AmountVerificationResult(
            input_amount=f.USDT.amount_from_base_units(1),
            status=AmountVerificationStatus.VERIFIED_UNPROFITABLE,
            buy_quote=f.candidate().buy_quote,
            sell_quote=f.candidate().sell_quote,
            current_buy_output=f.candidate().buy_quote.output_amount,
            current_sell_output=f.candidate().sell_quote.output_amount,
            profit_result=f.profit_result(net_roi="0.5", passed=False),
        )
        assert unprofitable.confirmation_status is AmountConfirmationStatus.UNCONFIRMED

    def test_route_unavailable_is_partial_not_unconfirmed(self) -> None:
        """ROUTE_UNAVAILABLE не означает убыточность (11 §51)."""
        result = AmountVerificationResult(
            input_amount=f.USDT.amount_from_base_units(1),
            status=AmountVerificationStatus.ROUTE_UNAVAILABLE,
        )
        assert result.confirmation_status is AmountConfirmationStatus.PARTIAL


class TestConfirmationResult:
    def _result(self, statuses: tuple[AmountVerificationStatus, ...]) -> ConfirmationResult:
        candidate = f.candidate()
        results = []
        for index, status in enumerate(statuses, start=1):
            if status in {
                AmountVerificationStatus.VERIFIED_PROFITABLE,
                AmountVerificationStatus.VERIFIED_UNPROFITABLE,
            }:
                passed = status is AmountVerificationStatus.VERIFIED_PROFITABLE
                results.append(
                    AmountVerificationResult(
                        input_amount=f.USDT.amount_from_base_units(index),
                        status=status,
                        buy_quote=candidate.buy_quote,
                        sell_quote=candidate.sell_quote,
                        current_buy_output=candidate.buy_quote.output_amount,
                        current_sell_output=candidate.sell_quote.output_amount,
                        profit_result=f.profit_result(
                            net_roi="1.5" if passed else "0.5", passed=passed
                        ),
                    )
                )
            else:
                results.append(
                    AmountVerificationResult(
                        input_amount=f.USDT.amount_from_base_units(index), status=status
                    )
                )
        return ConfirmationResult(
            k_id=f.KId.from_sequence(1),
            opportunity_id=f.OpportunityId("44444444-4444-4444-8444-444444444444"),
            revision=1,
            job_status=JobStatus.CONFIRMED,
            amount_results=tuple(results),
            completed_at=f.NOW,
        )

    def test_counts_by_confirmation_status(self) -> None:
        result = self._result(
            (
                AmountVerificationStatus.VERIFIED_PROFITABLE,
                AmountVerificationStatus.VERIFIED_UNPROFITABLE,
                AmountVerificationStatus.UNKNOWN,
                AmountVerificationStatus.ROUTE_UNAVAILABLE,
            )
        )
        assert result.confirmed_count == 1
        assert result.unconfirmed_count == 1
        assert result.partial_count == 2
        assert result.has_confirmed_amount

    def test_partial_only_is_not_confirmation(self) -> None:
        """PARTIAL нельзя считать CONFIRMED (CLAUDE.md §26)."""
        result = self._result((AmountVerificationStatus.UNKNOWN,))
        assert not result.has_confirmed_amount


class TestLevel2Job:
    def test_expiration_and_terminal_states(self) -> None:
        job = f.level2_job()
        assert not job.is_expired(f.NOW)
        assert job.is_expired(f.NOW + timedelta(minutes=5))
        assert not job.is_terminal
        assert f.level2_job(status=JobStatus.CONFIRMED).is_terminal

    def test_attempt_count_does_not_imply_success(self) -> None:
        """attempt_count не означает успешного выполнения (36 §39)."""
        job = f.level2_job().replace(attempt_count=3)
        assert job.attempt_count == 3
        assert job.status is JobStatus.QUEUED

    def test_rejects_expiry_before_creation(self) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            f.level2_job().replace(expires_at=f.NOW - timedelta(seconds=1))

    def test_k_id_space_is_separate_from_v_id(self) -> None:
        job = f.level2_job()
        opportunity: Opportunity = f.opportunity()
        assert str(job.k_id) != str(opportunity.v_id)
        assert job.k_id.sequence == opportunity.v_id.sequence


class TestCandidateIsNotPersistedEntity:
    def test_candidate_has_no_persistent_identifier(self) -> None:
        """Решение D-1: Candidate — промежуточный результат, а не сущность БД."""
        assert "candidate_id" not in Candidate.model_fields
