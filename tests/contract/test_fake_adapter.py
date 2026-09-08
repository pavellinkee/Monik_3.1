"""FakeAdapter обязан соответствовать общему контракту адаптеров."""

from __future__ import annotations

from decimal import Decimal

import pytest

from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError
from monik.infrastructure.providers import AggregatorAdapter, FakeAdapter, QuoteRequest
from monik.services.observability import FakeClock
from tests import factories as f

from .adapter_contract import AdapterContractTests


class TestFakeAdapterContract(AdapterContractTests):
    """Прогон общего contract suite на тестовой реализации."""

    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return FakeAdapter(ProviderId.ONEINCH, clock, rate=Decimal("0.05"))

    def expected_provider(self) -> ProviderId:
        return ProviderId.ONEINCH

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return FakeAdapter(ProviderId.ONEINCH, clock, error=ProviderError("upstream unavailable"))


class TestFakeAdapterBehaviour:
    """Поведение самой тестовой реализации."""

    def _adapter(self, **kwargs: object) -> FakeAdapter:
        return FakeAdapter(ProviderId.ZERO_X, FakeClock(f.NOW), **kwargs)  # type: ignore[arg-type]

    def _request(self) -> QuoteRequest:
        return QuoteRequest(
            network_id=f.POLYGON,
            operation=OperationType.BUY,
            input_token=f.USDT,
            output_token=f.AAVE,
            input_amount=f.USDT.amount_from_base_units(100_000_000),
            request_id=f.RequestId.generate(),
        )

    async def test_rate_is_applied_with_target_decimals(self) -> None:
        adapter = self._adapter(rate=Decimal("0.05"))
        quote = await adapter.get_quote(self._request())
        assert quote.output_amount.as_decimal == Decimal("5.000000000000000000")
        assert quote.output_amount.decimals == 18

    async def test_records_calls(self) -> None:
        adapter = self._adapter()
        await adapter.get_quote(self._request())
        assert len(adapter.quote_calls) == 1

    async def test_fixed_route_mismatch_is_reported(self) -> None:
        adapter = self._adapter(fixed_route_outcome=RouteValidationOutcome.MISMATCH)
        validation = await adapter.validate_fixed_route(self._request())
        assert validation.outcome is RouteValidationOutcome.MISMATCH
        assert validation.quote is None
        assert validation.observed_fingerprint is not None

    async def test_fixed_route_unsupported_is_reported(self) -> None:
        adapter = self._adapter(fixed_route_outcome=RouteValidationOutcome.UNSUPPORTED)
        validation = await adapter.validate_fixed_route(self._request())
        assert validation.outcome is RouteValidationOutcome.UNSUPPORTED
        assert not validation.is_reproduced

    async def test_default_fee_discovery_is_empty(self) -> None:
        """Fake не выдумывает комиссии, которых не знает (06 §39)."""
        assert await self._adapter().discover_fees(f.POLYGON) == ()


class TestQuoteRequestValidation:
    def _request(self, **overrides: object) -> QuoteRequest:
        base: dict[str, object] = {
            "network_id": f.POLYGON,
            "operation": OperationType.BUY,
            "input_token": f.USDT,
            "output_token": f.AAVE,
            "input_amount": f.USDT.amount_from_base_units(100_000_000),
            "request_id": f.RequestId.generate(),
        }
        base.update(overrides)
        return QuoteRequest(**base)  # type: ignore[arg-type]

    def test_rejects_identical_tokens(self) -> None:
        with pytest.raises(ValueError, match="must differ"):
            self._request(output_token=f.USDT)

    def test_rejects_zero_amount(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            self._request(input_amount=f.USDT.amount_from_base_units(0))

    def test_rejects_amount_with_wrong_decimals(self) -> None:
        with pytest.raises(ValueError, match="decimals"):
            self._request(input_amount=f.AAVE.amount_from_base_units(100))

    def test_rejects_cross_network_tokens(self) -> None:
        foreign = f.Token(
            network_id=f.NetworkId("ethereum"),
            address=f.AAVE.address,
            symbol="AAVE",
            decimals=18,
        )
        with pytest.raises(ValueError, match="another network"):
            self._request(output_token=foreign)
