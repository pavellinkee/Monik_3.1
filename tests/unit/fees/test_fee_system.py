"""Тесты Fee System."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest

from monik.config.sections.fees import FeeConfig
from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.services.fees import (
    FeeContext,
    FeeService,
    PercentageFeePolicy,
    QuoteInclusiveFeePolicy,
    UnknownFeePolicy,
)
from monik.services.observability import FakeClock
from tests import factories as f


def _context(**overrides: object) -> FeeContext:
    base: dict[str, object] = {
        "provider_id": ProviderId.ONEINCH,
        "network_id": f.POLYGON,
        "operation": OperationType.BUY,
        "input_token": f.USDT.key,
        "output_token": f.AAVE.key,
        "input_amount": f.USDT.amount_from_base_units(100_000_000),
    }
    base.update(overrides)
    return FeeContext(**base)  # type: ignore[arg-type]


class TestPolicies:
    def test_quote_inclusive_fee_is_not_deducted_again(self) -> None:
        """Комиссия внутри котировки не вычитается повторно (01 §29)."""
        policy = QuoteInclusiveFeePolicy(ProviderId.ONEINCH, source="test")
        fee = policy.components(_context(), observed_at=f.NOW)[0]
        assert fee.inclusion is CostInclusion.INCLUDED_IN_QUOTE
        assert not fee.is_deductible
        assert fee.is_known

    def test_percentage_fee_uses_declared_base(self) -> None:
        """База процента задана явно, а не угадывается (09 §57)."""
        policy = PercentageFeePolicy(ProviderId.ZERO_X, rate_bps=25, source="test")
        fee = policy.components(_context(), observed_at=f.NOW)[0]
        assert fee.known_amount == Decimal("0.25")
        assert fee.currency == f.USDT.key
        assert fee.is_deductible

    def test_percentage_fee_scales_with_amount(self) -> None:
        policy = PercentageFeePolicy(ProviderId.ZERO_X, rate_bps=25, source="test")
        large = policy.components(
            _context(input_amount=f.USDT.amount_from_base_units(1_000_000_000)),
            observed_at=f.NOW,
        )[0]
        assert large.known_amount == Decimal("2.50")

    def test_negative_rate_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            PercentageFeePolicy(ProviderId.ZERO_X, rate_bps=-1, source="test")

    def test_unknown_policy_has_no_amount(self) -> None:
        """UNKNOWN не превращается в ноль (07 §15)."""
        policy = UnknownFeePolicy(
            ProviderId.VELORA, source="test", reason="fee model not documented"
        )
        fee = policy.components(_context(), observed_at=f.NOW)[0]
        assert fee.status is FeeStatus.UNKNOWN
        assert fee.amount is None
        assert not fee.is_known


class TestFeeService:
    def _service(self, clock: FakeClock, **policies: object) -> FeeService:
        registry = {
            ProviderId.ONEINCH: QuoteInclusiveFeePolicy(ProviderId.ONEINCH, source="test"),
        }
        registry.update(policies)  # type: ignore[arg-type]
        return FeeService(FeeConfig(freshness_seconds=3600), clock, policies=registry)

    async def test_returns_policy_components(self) -> None:
        service = self._service(FakeClock(f.NOW))
        fees = await service.fees_for(_context())
        assert len(fees) == 1
        assert fees[0].fee_type is FeeType.AGGREGATOR

    async def test_snapshot_is_reused_while_fresh(self) -> None:
        """Одинаковый fee-запрос не повторяется каждый цикл (01 §31)."""
        clock = FakeClock(f.NOW)
        service = self._service(clock)
        first = await service.snapshot_for(_context())
        second = await service.snapshot_for(_context())
        assert first.snapshot_id == second.snapshot_id

    async def test_snapshot_is_rebuilt_when_stale(self) -> None:
        clock = FakeClock(f.NOW)
        service = self._service(clock)
        first = await service.snapshot_for(_context())
        clock.advance(timedelta(hours=2))
        second = await service.snapshot_for(_context())
        assert first.snapshot_id != second.snapshot_id

    async def test_context_is_not_over_generalized(self) -> None:
        """Разные контексты не смешиваются (07 §46)."""
        service = self._service(FakeClock(f.NOW))
        buy = await service.snapshot_for(_context(operation=OperationType.BUY))
        sell = await service.snapshot_for(_context(operation=OperationType.SELL))
        assert buy.snapshot_id != sell.snapshot_id

    async def test_route_context_separates_snapshots(self) -> None:
        service = self._service(FakeClock(f.NOW))
        without = await service.snapshot_for(_context())
        with_route = await service.snapshot_for(
            _context(route_fingerprint=f.candidate().buy_quote.route.fingerprint)
        )
        assert without.snapshot_id != with_route.snapshot_id

    async def test_unregistered_provider_yields_unknown(self) -> None:
        """Отсутствие policy не означает отсутствие комиссии (07 §15)."""
        service = self._service(FakeClock(f.NOW))
        fees = await service.fees_for(_context(provider_id=ProviderId.UNISWAP))
        assert len(fees) == 1
        assert fees[0].status is FeeStatus.UNKNOWN
        assert fees[0].amount is None

    async def test_concurrent_identical_requests_are_merged(self) -> None:
        """Одновременные одинаковые запросы объединяются (07 §60)."""
        clock = FakeClock(f.NOW)
        service = self._service(clock)
        results = await asyncio.gather(*(service.snapshot_for(_context()) for _ in range(5)))
        assert len({snapshot.snapshot_id for snapshot in results}) == 1
        assert service.merged_requests == 4

    async def test_refresh_groups_duplicate_contexts(self) -> None:
        """Одинаковые контексты не обрабатываются дважды (07 §33)."""
        service = self._service(FakeClock(f.NOW))
        snapshots = await service.refresh((_context(), _context(), _context()))
        assert len(snapshots) == 1

    async def test_refresh_rebuilds_snapshots(self) -> None:
        service = self._service(FakeClock(f.NOW))
        before = await service.snapshot_for(_context())
        after = (await service.refresh((_context(),)))[0]
        assert before.snapshot_id != after.snapshot_id

    async def test_invalidate_clears_cache(self) -> None:
        service = self._service(FakeClock(f.NOW))
        first = await service.snapshot_for(_context())
        service.invalidate(_context())
        second = await service.snapshot_for(_context())
        assert first.snapshot_id != second.snapshot_id

    async def test_snapshot_records_version(self) -> None:
        service = self._service(FakeClock(f.NOW))
        snapshot = await service.snapshot_for(_context())
        assert snapshot.version >= 1

    async def test_snapshot_detects_unknown_components(self) -> None:
        service = self._service(FakeClock(f.NOW))
        snapshot = await service.snapshot_for(_context(provider_id=ProviderId.VELORA))
        assert snapshot.has_unknown
