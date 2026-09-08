"""Level 1: группировка, ранжирование, дедупликация и валидация котировок."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.quotes import QuoteStatus
from monik.domain.models.opportunity import Candidate, Opportunity, opportunity_fingerprint
from monik.domain.models.quote import Quote
from monik.domain.value_objects.fingerprints import OpportunityFingerprint
from monik.infrastructure.providers.contract import QuoteRequest
from monik.services.level1 import (
    DeduplicationGuard,
    group_candidates,
    quote_rejection_reason,
    rank_groups,
)
from tests import factories as f

MAX_AGE = timedelta(seconds=30)


def buy_request(input_amount_raw: int = 100_000_000) -> QuoteRequest:
    return QuoteRequest(
        network_id=f.POLYGON,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_amount=f.USDT.amount_from_base_units(input_amount_raw),
        request_id=f.RequestId.generate(),
    )


def buy_quote(
    *,
    provider_id: ProviderId = ProviderId.ONEINCH,
    input_raw: int = 100_000_000,
    output_raw: int = 5 * 10**18,
) -> Quote:
    return f.quote(
        provider_id=provider_id,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=input_raw,
        output_raw=output_raw,
    )


def sell_quote(
    *,
    provider_id: ProviderId = ProviderId.ZERO_X,
    input_raw: int = 5 * 10**18,
    output_raw: int = 101_500_000,
) -> Quote:
    return f.quote(
        provider_id=provider_id,
        operation=OperationType.SELL,
        input_token=f.AAVE,
        output_token=f.USDT,
        input_raw=input_raw,
        output_raw=output_raw,
    )


def candidate(
    *,
    input_raw: int = 100_000_000,
    buy_output_raw: int = 5 * 10**18,
    sell_output_raw: int = 101_500_000,
    net_roi: str = "1.20",
    buy_provider: ProviderId = ProviderId.ONEINCH,
    sell_provider: ProviderId = ProviderId.ZERO_X,
) -> Candidate:
    """Кандидат с заданным предварительным результатом."""
    buy = buy_quote(provider_id=buy_provider, input_raw=input_raw, output_raw=buy_output_raw)
    sell = sell_quote(
        provider_id=sell_provider, input_raw=buy_output_raw, output_raw=sell_output_raw
    )
    result = f.profit_result(
        input_raw=input_raw,
        output_raw=sell_output_raw,
        net_roi=net_roi,
    )
    return Candidate(
        scan_id=f.ScanId.generate(),
        buy_quote=buy,
        sell_quote=sell,
        preliminary_result=result,
        detected_at=f.NOW,
    )


# --- валидация ------------------------------------------------------------


def test_matching_quote_is_accepted() -> None:
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ONEINCH,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=request.input_amount.raw,
        output_raw=5 * 10**18,
    )
    reason = quote_rejection_reason(
        quote, request, provider_id=ProviderId.ONEINCH, now=f.NOW, max_age=MAX_AGE
    )
    assert reason is None


def test_quote_from_another_provider_is_rejected() -> None:
    """Подмена провайдера не допускается (``02`` §23)."""
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ZERO_X,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=request.input_amount.raw,
        output_raw=5 * 10**18,
    )
    reason = quote_rejection_reason(
        quote, request, provider_id=ProviderId.ONEINCH, now=f.NOW, max_age=MAX_AGE
    )
    assert reason == "quote was returned by a different provider"


def test_quote_with_wrong_amount_is_rejected() -> None:
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ONEINCH,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=50_000_000,
        output_raw=5 * 10**18,
    )
    reason = quote_rejection_reason(
        quote, request, provider_id=ProviderId.ONEINCH, now=f.NOW, max_age=MAX_AGE
    )
    assert reason == "quote input amount does not match the request"


def test_zero_output_quote_is_rejected() -> None:
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ONEINCH,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=request.input_amount.raw,
        output_raw=0,
    )
    reason = quote_rejection_reason(
        quote, request, provider_id=ProviderId.ONEINCH, now=f.NOW, max_age=MAX_AGE
    )
    assert reason == "quote output amount is zero"


def test_non_valid_status_is_rejected() -> None:
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ONEINCH,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=request.input_amount.raw,
        output_raw=5 * 10**18,
    ).replace(status=QuoteStatus.EXPIRED)
    reason = quote_rejection_reason(
        quote, request, provider_id=ProviderId.ONEINCH, now=f.NOW, max_age=MAX_AGE
    )
    assert reason == "quote status is expired"


def test_stale_quote_is_rejected() -> None:
    request = buy_request()
    quote = f.quote(
        provider_id=ProviderId.ONEINCH,
        operation=OperationType.BUY,
        input_token=f.USDT,
        output_token=f.AAVE,
        input_raw=request.input_amount.raw,
        output_raw=5 * 10**18,
    )
    reason = quote_rejection_reason(
        quote,
        request,
        provider_id=ProviderId.ONEINCH,
        now=f.NOW + timedelta(minutes=5),
        max_age=MAX_AGE,
    )
    assert reason == "quote is not fresh enough for this scan"


# --- группировка ----------------------------------------------------------


def test_amounts_with_the_same_route_share_one_group() -> None:
    """Разные суммы одного маршрута образуют одну Opportunity (``10`` §54)."""
    groups = group_candidates(
        (
            candidate(input_raw=100_000_000),
            candidate(input_raw=500_000_000, buy_output_raw=25 * 10**18),
        )
    )
    assert len(groups) == 1
    assert len(groups[0].amounts) == 2


def test_different_provider_pairs_form_different_groups() -> None:
    groups = group_candidates(
        (
            candidate(buy_provider=ProviderId.ONEINCH, sell_provider=ProviderId.ZERO_X),
            candidate(buy_provider=ProviderId.ZERO_X, sell_provider=ProviderId.ONEINCH),
        )
    )
    assert len(groups) == 2


def test_duplicate_amount_inside_a_group_is_ignored() -> None:
    groups = group_candidates((candidate(), candidate()))
    assert len(groups) == 1
    assert len(groups[0].amounts) == 1


def test_group_fingerprint_matches_the_created_opportunity() -> None:
    """Отпечаток до создания совпадает с отпечатком модели."""
    group = group_candidates((candidate(),))[0]
    expected = opportunity_fingerprint(
        routes=group.routes,
        buy_provider_id=group.buy_provider_id,
        sell_provider_id=group.sell_provider_id,
    )
    assert group.fingerprint == expected
    assert isinstance(group.fingerprint, OpportunityFingerprint)


def test_amounts_are_ordered_ascending() -> None:
    groups = group_candidates(
        (
            candidate(input_raw=500_000_000, buy_output_raw=25 * 10**18),
            candidate(input_raw=100_000_000),
        )
    )
    raw = [amount.input_amount.raw for amount in groups[0].amounts]
    assert raw == sorted(raw)


# --- ранжирование ---------------------------------------------------------


def test_groups_are_ranked_by_preliminary_net_roi() -> None:
    """Более привлекательный кандидат обслуживается первым (``02`` §49-50)."""
    weak = group_candidates((candidate(net_roi="1.10", buy_provider=ProviderId.ONEINCH),))[0]
    strong = group_candidates(
        (
            candidate(
                net_roi="4.00",
                buy_provider=ProviderId.ZERO_X,
                sell_provider=ProviderId.ONEINCH,
            ),
        )
    )[0]
    ranked = rank_groups((weak, strong))
    assert ranked[0] is strong


def test_ranking_is_stable_for_equal_metrics() -> None:
    """Порядок не зависит от порядка завершения корутин (``02`` §94)."""
    first = group_candidates((candidate(net_roi="2.00"),))[0]
    second = group_candidates(
        (
            candidate(
                net_roi="2.00",
                buy_provider=ProviderId.ZERO_X,
                sell_provider=ProviderId.ONEINCH,
            ),
        )
    )[0]
    assert rank_groups((first, second)) == rank_groups((second, first))


# --- дедупликация ---------------------------------------------------------


class _Store:
    """Хранилище, возвращающее заранее заданный результат поиска."""

    def __init__(self, existing: Opportunity | object | None = None) -> None:
        self.existing = existing
        self.lookups = 0

    async def create_with_job(self, opportunity: object, job: object) -> None:
        raise AssertionError("dedup guard must not create opportunities")

    async def find_recent_by_fingerprint(
        self, fingerprint: OpportunityFingerprint, *, since: object
    ) -> object | None:
        self.lookups += 1
        return self.existing


async def test_repeated_fingerprint_is_a_duplicate() -> None:
    guard = DeduplicationGuard(_Store(), window=timedelta(minutes=5))
    fingerprint = group_candidates((candidate(),))[0].fingerprint

    assert await guard.is_duplicate(fingerprint, now=f.NOW) is False
    guard.remember(fingerprint)
    assert await guard.is_duplicate(fingerprint, now=f.NOW) is True
    assert guard.duplicates == 1


async def test_stored_opportunity_in_window_is_a_duplicate() -> None:
    store = _Store(existing=object())
    guard = DeduplicationGuard(store, window=timedelta(minutes=5))
    fingerprint = group_candidates((candidate(),))[0].fingerprint

    assert await guard.is_duplicate(fingerprint, now=f.NOW) is True
    assert store.lookups == 1


async def test_zero_window_skips_the_lookup() -> None:
    """Нулевое окно отключает поиск и не создаёт лишних запросов к БД."""
    store = _Store(existing=object())
    guard = DeduplicationGuard(store, window=timedelta(0))
    fingerprint = group_candidates((candidate(),))[0].fingerprint

    assert await guard.is_duplicate(fingerprint, now=f.NOW) is False
    assert store.lookups == 0


@pytest.mark.parametrize("net_roi", ["-5.00", "0.00", "12.50"])
def test_ranking_handles_any_sign_of_roi(net_roi: str) -> None:
    """Отрицательный ROI не превращается в ноль (``09`` §22)."""
    group = group_candidates((candidate(net_roi=net_roi),))[0]
    ranked = rank_groups((group,))
    assert ranked == (group,)
    assert group.candidates[0].preliminary_result.net_roi is not None
    assert group.candidates[0].preliminary_result.net_roi.value == Decimal(net_roi)
