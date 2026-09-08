"""Тесты Gas System."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest

from monik.domain.enums.fees import FeeStatus
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.services.gas import GasEstimator, RpcGasPriceProvider, StaticGasPriceProvider
from monik.services.observability import FakeClock
from tests import factories as f
from tests.unit.providers.support import resource_manager

NATIVE_TOKENS = {str(f.POLYGON): f.WMATIC.key}


def _estimator(clock: FakeClock, *providers: object) -> GasEstimator:
    return GasEstimator(
        clock,
        price_providers=providers
        or (  # type: ignore[arg-type]
            StaticGasPriceProvider(clock, prices={str(f.POLYGON): 100_000_000_000}),
        ),
        native_tokens=NATIVE_TOKENS,
    )


class TestGasEstimator:
    async def test_computes_cost_from_units_and_price(self) -> None:
        clock = FakeClock(f.NOW)
        gas = await _estimator(clock).estimate(f.POLYGON, gas_units=200_000)
        assert gas.is_known
        # 200000 * 100 gwei = 0.02 native token
        assert gas.known_cost_native == Decimal("0.02")
        assert gas.native_token == f.WMATIC.key

    async def test_unknown_units_produce_unknown_gas(self) -> None:
        """Отсутствие gas units не превращается в ноль (09 §16)."""
        clock = FakeClock(f.NOW)
        gas = await _estimator(clock).estimate(f.POLYGON, gas_units=None)
        assert gas.status is FeeStatus.UNKNOWN
        assert gas.cost_native is None
        with pytest.raises(ValueError, match="must not be treated as zero"):
            _ = gas.known_cost_native

    async def test_unavailable_price_produces_unknown_gas(self) -> None:
        clock = FakeClock(f.NOW)
        estimator = GasEstimator(
            clock,
            price_providers=(StaticGasPriceProvider(clock, prices={}),),
            native_tokens=NATIVE_TOKENS,
        )
        gas = await estimator.estimate(f.POLYGON, gas_units=200_000)
        assert gas.status is FeeStatus.UNKNOWN
        assert gas.gas_units == 200_000
        assert gas.cost_native is None

    async def test_unknown_native_token_produces_unknown_gas(self) -> None:
        clock = FakeClock(f.NOW)
        estimator = GasEstimator(
            clock,
            price_providers=(StaticGasPriceProvider(clock, prices={str(f.POLYGON): 1}),),
            native_tokens={},
        )
        gas = await estimator.estimate(f.POLYGON, gas_units=1)
        assert gas.status is FeeStatus.UNKNOWN

    async def test_first_available_provider_wins(self) -> None:
        clock = FakeClock(f.NOW)
        empty = StaticGasPriceProvider(clock, prices={})
        available = StaticGasPriceProvider(clock, prices={str(f.POLYGON): 50_000_000_000})
        gas = await _estimator(clock, empty, available).estimate(f.POLYGON, gas_units=100_000)
        assert gas.known_cost_native == Decimal("0.005")

    def test_requires_at_least_one_provider(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            GasEstimator(FakeClock(f.NOW), price_providers=(), native_tokens=NATIVE_TOKENS)

    async def test_exact_arithmetic_is_used(self) -> None:
        """Финансовые значения не проходят через float (09 §3)."""
        clock = FakeClock(f.NOW)
        estimator = _estimator(clock, StaticGasPriceProvider(clock, prices={str(f.POLYGON): 1}))
        gas = await estimator.estimate(f.POLYGON, gas_units=1)
        assert gas.known_cost_native == Decimal("1") / Decimal(10) ** 18


class TestRpcGasPriceProvider:
    def _provider(self, clock: FakeClock, responses: list[HttpResponse]) -> RpcGasPriceProvider:
        return RpcGasPriceProvider(
            http=FakeHttpClient(responses),
            resources=resource_manager(clock),
            clock=clock,
            rpc_urls={str(f.POLYGON): "https://polygon-rpc.com"},
            freshness_seconds=60,
            priority_fee_wei=30_000_000_000,
        )

    def _result(self, value: object) -> HttpResponse:
        return HttpResponse(status_code=200, text=json.dumps({"result": value}))

    async def test_uses_eip1559_when_base_fee_available(self) -> None:
        clock = FakeClock(f.NOW)
        provider = self._provider(
            clock,
            [
                self._result("0x3b9aca00"),
                self._result({"baseFeePerGas": ["0x2540be400", "0x3b9aca00"]}),
            ],
        )
        price = await provider.gas_price(f.POLYGON)
        assert price is not None
        assert price.base_fee_wei == 1_000_000_000
        assert price.priority_fee_wei == 30_000_000_000
        assert price.wei_per_gas == 31_000_000_000

    async def test_falls_back_to_legacy_gas_price(self) -> None:
        clock = FakeClock(f.NOW)
        provider = self._provider(clock, [self._result("0x3b9aca00"), self._result(None)])
        price = await provider.gas_price(f.POLYGON)
        assert price is not None
        assert price.wei_per_gas == 1_000_000_000
        assert price.base_fee_wei is None

    async def test_unknown_network_returns_none(self) -> None:
        clock = FakeClock(f.NOW)
        provider = self._provider(clock, [])
        assert await provider.gas_price(f.NetworkId("arbitrum")) is None

    async def test_price_carries_freshness_window(self) -> None:
        clock = FakeClock(f.NOW)
        provider = self._provider(clock, [self._result("0x3b9aca00"), self._result(None)])
        price = await provider.gas_price(f.POLYGON)
        assert price is not None
        assert price.is_fresh(f.NOW)
        assert not price.is_fresh(f.NOW + timedelta(minutes=2))
