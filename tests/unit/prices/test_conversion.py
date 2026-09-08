"""Тесты источников цен и конвертации."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest

from monik.domain.errors import ProviderError
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.services.observability import FakeClock
from monik.services.prices import (
    AggregatorQuotePriceProvider,
    ConversionService,
    HttpPriceProvider,
    StaticPriceProvider,
    TokenPriceProvider,
)
from tests import factories as f
from tests.unit.providers.support import resource_manager

PAIR = (str(f.WMATIC.key), str(f.USDT.key))


def _static(clock: FakeClock, rate: str = "0.42") -> StaticPriceProvider:
    return StaticPriceProvider(clock, rates={PAIR: Decimal(rate)})


class TestStaticProvider:
    async def test_returns_configured_rate(self) -> None:
        clock = FakeClock(f.NOW)
        rate = await _static(clock).rate(f.WMATIC, f.USDT)
        assert rate is not None
        assert rate.rate == Decimal("0.42")
        assert rate.from_token == f.WMATIC.key

    async def test_unknown_pair_returns_none(self) -> None:
        """Неизвестный курс не подменяется выдуманным (09 §37)."""
        clock = FakeClock(f.NOW)
        assert await _static(clock).rate(f.USDT, f.AAVE) is None

    def test_satisfies_protocol(self) -> None:
        assert isinstance(_static(FakeClock(f.NOW)), TokenPriceProvider)


class TestAggregatorQuoteProvider:
    async def test_derives_rate_from_executable_quote(self) -> None:
        """Курс берётся из executable quote, а не из абстрактной цены (01 §17)."""
        from monik.domain.enums.providers import ProviderId
        from monik.infrastructure.providers import FakeAdapter

        clock = FakeClock(f.NOW)
        adapter = FakeAdapter(ProviderId.ONEINCH, clock, rate=Decimal("0.5"))
        provider = AggregatorQuotePriceProvider(adapter, clock, probe_amount_raw=10**18)
        rate = await provider.rate(f.WMATIC, f.USDT)
        assert rate is not None
        assert rate.rate == Decimal("0.5")

    async def test_provider_failure_yields_none(self) -> None:
        from monik.domain.enums.providers import ProviderId
        from monik.infrastructure.providers import FakeAdapter

        clock = FakeClock(f.NOW)
        adapter = FakeAdapter(ProviderId.ONEINCH, clock, error=ProviderError("unavailable"))
        provider = AggregatorQuotePriceProvider(adapter, clock, probe_amount_raw=10**18)
        assert await provider.rate(f.WMATIC, f.USDT) is None

    def test_probe_amount_must_be_positive(self) -> None:
        from monik.domain.enums.providers import ProviderId
        from monik.infrastructure.providers import FakeAdapter

        clock = FakeClock(f.NOW)
        with pytest.raises(ValueError, match="must be positive"):
            AggregatorQuotePriceProvider(
                FakeAdapter(ProviderId.ONEINCH, clock), clock, probe_amount_raw=0
            )


class TestHttpPriceProvider:
    def _provider(self, clock: FakeClock, http: FakeHttpClient) -> HttpPriceProvider:
        return HttpPriceProvider(
            http=http,
            resources=resource_manager(clock),
            clock=clock,
            endpoint="https://prices.example.com/rate",
        )

    async def test_parses_rate(self) -> None:
        clock = FakeClock(f.NOW)
        http = FakeHttpClient([HttpResponse(status_code=200, text=json.dumps({"rate": "0.37"}))])
        rate = await self._provider(clock, http).rate(f.WMATIC, f.USDT)
        assert rate is not None
        assert rate.rate == Decimal("0.37")

    async def test_float_rate_is_rejected(self) -> None:
        """Финансовое значение не приходит как binary float (09 §3)."""
        clock = FakeClock(f.NOW)
        http = FakeHttpClient([HttpResponse(status_code=200, text=json.dumps({"rate": 0.37}))] * 5)
        assert await self._provider(clock, http).rate(f.WMATIC, f.USDT) is None

    async def test_missing_rate_returns_none(self) -> None:
        clock = FakeClock(f.NOW)
        http = FakeHttpClient([HttpResponse(status_code=200, text="{}")])
        assert await self._provider(clock, http).rate(f.WMATIC, f.USDT) is None

    async def test_service_failure_returns_none(self) -> None:
        clock = FakeClock(f.NOW)
        http = FakeHttpClient([ProviderError("prices down")] * 5)
        assert await self._provider(clock, http).rate(f.WMATIC, f.USDT) is None


class TestConversionService:
    async def test_returns_fresh_rate(self) -> None:
        clock = FakeClock(f.NOW)
        service = ConversionService(clock, providers=(_static(clock),))
        rate = await service.rate(f.WMATIC, f.USDT)
        assert rate is not None
        assert rate.rate == Decimal("0.42")

    async def test_same_token_has_no_conversion(self) -> None:
        clock = FakeClock(f.NOW)
        service = ConversionService(clock, providers=(_static(clock),))
        assert await service.rate(f.USDT, f.USDT) is None

    async def test_stale_rate_is_not_reused(self) -> None:
        """Устаревший курс не используется бесконечно (09 §36)."""
        clock = FakeClock(f.NOW)
        service = ConversionService(
            clock,
            providers=(StaticPriceProvider(clock, rates={PAIR: Decimal("0.42")}, ttl_seconds=60),),
        )
        assert await service.rate(f.WMATIC, f.USDT) is not None
        clock.advance(timedelta(minutes=2))
        refreshed = await service.rate(f.WMATIC, f.USDT)
        assert refreshed is not None
        assert refreshed.observed_at == clock.now()

    async def test_falls_back_to_next_provider(self) -> None:
        clock = FakeClock(f.NOW)
        empty = StaticPriceProvider(clock, rates={})
        service = ConversionService(clock, providers=(empty, _static(clock)))
        assert await service.rate(f.WMATIC, f.USDT) is not None

    async def test_returns_none_when_all_providers_fail(self) -> None:
        clock = FakeClock(f.NOW)
        service = ConversionService(clock, providers=(StaticPriceProvider(clock, rates={}),))
        assert await service.rate(f.WMATIC, f.USDT) is None

    def test_requires_at_least_one_provider(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            ConversionService(FakeClock(f.NOW), providers=())

    async def test_direction_is_explicit(self) -> None:
        """Обратный курс не выводится из прямого (09 §38)."""
        clock = FakeClock(f.NOW)
        service = ConversionService(clock, providers=(_static(clock),))
        assert await service.rate(f.WMATIC, f.USDT) is not None
        assert await service.rate(f.USDT, f.WMATIC) is None
