"""Confirmation Policy: сведение статусов сумм в итог Job и Opportunity."""

from __future__ import annotations

import pytest

from monik.domain.enums.lifecycle import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
    OpportunityStatus,
)
from monik.domain.models.job import AmountVerificationResult, ConfirmationResult
from monik.services.level2 import job_status_for, opportunity_status_for
from tests import factories as f


def amount(status: AmountVerificationStatus, *, raw: int = 100_000_000) -> AmountVerificationResult:
    """Результат суммы без котировок: для терминальных статусов они не требуются."""
    if status in {
        AmountVerificationStatus.VERIFIED_PROFITABLE,
        AmountVerificationStatus.VERIFIED_UNPROFITABLE,
    }:
        profitable = status is AmountVerificationStatus.VERIFIED_PROFITABLE
        buy = f.quote(operation=f.OperationType.BUY, input_raw=raw)
        sell = f.quote(
            operation=f.OperationType.SELL,
            provider_id=f.ProviderId.ZERO_X,
            input_token=f.AAVE,
            output_token=f.USDT,
            input_raw=buy.output_amount.raw,
            output_raw=101_500_000,
        )
        return AmountVerificationResult(
            input_amount=buy.input_amount,
            status=status,
            buy_quote=buy,
            sell_quote=sell,
            current_buy_output=buy.output_amount,
            current_sell_output=sell.output_amount,
            profit_result=f.profit_result(passed=profitable),
        )
    return AmountVerificationResult(
        input_amount=f.USDT.amount_from_base_units(raw),
        status=status,
        rejection_reason="test",
    )


# --- статус Job -----------------------------------------------------------


def test_any_profitable_amount_confirms_the_job() -> None:
    results = (
        amount(AmountVerificationStatus.VERIFIED_PROFITABLE),
        amount(AmountVerificationStatus.VERIFIED_UNPROFITABLE, raw=500_000_000),
    )
    assert job_status_for(results) is JobStatus.CONFIRMED


def test_all_unprofitable_rejects_the_job() -> None:
    results = (amount(AmountVerificationStatus.VERIFIED_UNPROFITABLE),)
    assert job_status_for(results) is JobStatus.REJECTED


def test_route_unavailable_rejects_without_claiming_unprofitability() -> None:
    """ROUTE_UNAVAILABLE — определённый отрицательный вердикт, но не убыточность."""
    results = (amount(AmountVerificationStatus.ROUTE_UNAVAILABLE),)
    assert job_status_for(results) is JobStatus.REJECTED
    assert opportunity_status_for(results) is OpportunityStatus.ROUTE_UNAVAILABLE


@pytest.mark.parametrize(
    "status",
    [AmountVerificationStatus.UNKNOWN, AmountVerificationStatus.FAILED],
)
def test_undetermined_result_fails_instead_of_rejecting(
    status: AmountVerificationStatus,
) -> None:
    """Ошибка API не является признаком убыточности (``11`` §53-54)."""
    results = (amount(status),)
    assert job_status_for(results) is JobStatus.FAILED


def test_all_expired_marks_the_job_expired() -> None:
    results = (amount(AmountVerificationStatus.EXPIRED),)
    assert job_status_for(results) is JobStatus.EXPIRED
    assert opportunity_status_for(results) is OpportunityStatus.EXPIRED


def test_empty_result_set_fails() -> None:
    assert job_status_for(()) is JobStatus.FAILED
    assert opportunity_status_for(()) is OpportunityStatus.FAILED


# --- статус Opportunity ---------------------------------------------------


def test_all_profitable_confirms_the_opportunity() -> None:
    results = (
        amount(AmountVerificationStatus.VERIFIED_PROFITABLE),
        amount(AmountVerificationStatus.VERIFIED_PROFITABLE, raw=500_000_000),
    )
    assert opportunity_status_for(results) is OpportunityStatus.CONFIRMED


def test_mixed_result_is_partial() -> None:
    """Смешанный результат не скрывается (``11`` §46)."""
    results = (
        amount(AmountVerificationStatus.VERIFIED_PROFITABLE),
        amount(AmountVerificationStatus.UNKNOWN, raw=500_000_000),
    )
    assert opportunity_status_for(results) is OpportunityStatus.PARTIAL


def test_unprofitable_and_route_unavailable_is_not_route_unavailable() -> None:
    results = (
        amount(AmountVerificationStatus.VERIFIED_UNPROFITABLE),
        amount(AmountVerificationStatus.ROUTE_UNAVAILABLE, raw=500_000_000),
    )
    assert opportunity_status_for(results) is OpportunityStatus.UNPROFITABLE


# --- confirmation rate ----------------------------------------------------


def test_partial_is_excluded_from_confirmation_counts() -> None:
    """``PARTIAL`` не смешивается с подтверждёнными и опровергнутыми (``CLAUDE.md`` §27)."""
    results = (
        amount(AmountVerificationStatus.VERIFIED_PROFITABLE),
        amount(AmountVerificationStatus.VERIFIED_UNPROFITABLE, raw=200_000_000),
        amount(AmountVerificationStatus.UNKNOWN, raw=500_000_000),
    )
    result = ConfirmationResult(
        k_id=f.KId("#K1"),
        opportunity_id=f.OpportunityId.generate(),
        revision=1,
        job_status=job_status_for(results),
        amount_results=results,
        completed_at=f.NOW,
    )
    assert result.confirmed_count == 1
    assert result.unconfirmed_count == 1
    assert result.partial_count == 1
    assert result.has_confirmed_amount is True
    assert results[2].confirmation_status is AmountConfirmationStatus.PARTIAL
