"""Unit-тесты адаптера 0x."""

from __future__ import annotations

import pytest

from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    ProviderError,
    RateLimitError,
    UnsupportedError,
)
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.infrastructure.providers import QuoteRequest
from monik.infrastructure.providers.zero_x import ZeroXAdapter, endpoints
from monik.services.observability import FakeClock
from tests import factories as f

from .support import http_returning, provider_config, resource_manager, secret

PRICE_PAYLOAD = {
    "buyAmount": "5140000000000000000",
    "sellAmount": "100000000",
    "gas": "180000",
    "route": {
        "fills": [
            {"source": "QuickSwap_V3", "proportionBps": "6000"},
            {"source": "SushiSwap", "proportionBps": "4000"},
        ]
    },
}


def _adapter(http: FakeHttpClient, clock: FakeClock | None = None) -> ZeroXAdapter:
    active = clock or FakeClock(f.NOW)
    return ZeroXAdapter(
        provider_config(ProviderId.ZERO_X),
        http=http,
        resources=resource_manager(active),
        clock=active,
        api_key=secret(),
    )


def _request(**overrides: object) -> QuoteRequest:
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


class TestRequestBuilding:
    async def test_uses_indicative_price_endpoint(self) -> None:
        """Monik не исполняет свопы, поэтому используется /price (01 §55)."""
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert http.last_request().url == f"{endpoints.DEFAULT_BASE_URL}{endpoints.PRICE_PATH}"

    async def test_sends_documented_parameters(self) -> None:
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        params = http.last_request().params
        assert params["chainId"] == "137"
        assert params["sellToken"] == str(f.USDT.address)
        assert params["buyToken"] == str(f.AAVE.address)
        assert params["sellAmount"] == "100000000"

    async def test_sends_api_key_and_version_headers(self) -> None:
        """Схема аутентификации 0x отличается от Bearer."""
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        headers = http.last_request().headers
        assert headers[endpoints.API_VERSION_HEADER] == endpoints.API_VERSION
        assert headers[endpoints.API_KEY_HEADER]
        assert "Authorization" not in headers

    async def test_unsupported_network_is_reported(self) -> None:
        http = http_returning(PRICE_PAYLOAD)
        source = f.Token(
            network_id=f.NetworkId("base"), address=f.USDT.address, symbol="USDT", decimals=6
        )
        target = f.Token(
            network_id=f.NetworkId("base"), address=f.AAVE.address, symbol="AAVE", decimals=18
        )
        with pytest.raises(UnsupportedError):
            await _adapter(http).get_quote(
                _request(
                    network_id=f.NetworkId("base"),
                    input_token=source,
                    output_token=target,
                    input_amount=source.amount_from_base_units(1_000_000),
                )
            )
        assert http.call_count == 0


class TestResponseParsing:
    async def test_parses_buy_amount(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.output_amount.raw == 5_140_000_000_000_000_000

    async def test_parses_gas(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.estimated_gas_units == 180_000

    async def test_route_records_all_fill_sources(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.route.steps[0].protocol == "QuickSwap_V3+SushiSwap"

    async def test_fill_order_does_not_change_fingerprint(self) -> None:
        first = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        reordered = dict(PRICE_PAYLOAD)
        reordered["route"] = {"fills": list(reversed(PRICE_PAYLOAD["route"]["fills"]))}  # type: ignore[index]
        second = await _adapter(http_returning(reordered)).get_quote(_request())
        assert first.route.fingerprint == second.route.fingerprint

    async def test_missing_route_does_not_invent_steps(self) -> None:
        payload = {"buyAmount": "1", "sellAmount": "100000000"}
        quote = await _adapter(http_returning(payload)).get_quote(_request())
        assert quote.route.steps[0].protocol == "0x_aggregate"

    async def test_sell_amount_mismatch_is_rejected(self) -> None:
        """Ответ на другую сумму невалиден (06 §37)."""
        payload = {**PRICE_PAYLOAD, "sellAmount": "999"}
        with pytest.raises(DataError, match="different sell amount"):
            await _adapter(http_returning(payload)).get_quote(_request())

    async def test_missing_buy_amount_is_data_error(self) -> None:
        with pytest.raises(DataError, match="buyAmount"):
            await _adapter(http_returning({"sellAmount": "100000000"})).get_quote(_request())

    async def test_float_amount_is_rejected(self) -> None:
        with pytest.raises(DataError, match="non-integer amount"):
            await _adapter(http_returning({"buyAmount": 5.14})).get_quote(_request())

    async def test_output_is_marked_fee_inclusive(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.raw_output_amount_includes_fees is True


class TestErrorTranslation:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (429, RateLimitError),
            (401, AuthenticationError),
            (500, ProviderError),
            (422, DataError),
        ],
    )
    async def test_http_status_is_normalized(self, status: int, expected: type[Exception]) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=status, text="{}"))
        with pytest.raises(expected):
            await _adapter(http).get_quote(_request())


class TestFixedRoute:
    async def test_same_fills_are_reproduced(self) -> None:
        adapter = _adapter(http_returning(PRICE_PAYLOAD))
        original = await adapter.get_quote(_request())
        validation = await adapter.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.REPRODUCED

    async def test_changed_fills_are_mismatch(self) -> None:
        original = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        changed = _adapter(
            http_returning(
                {
                    **PRICE_PAYLOAD,
                    "route": {"fills": [{"source": "Balancer_V2"}]},
                }
            )
        )
        validation = await changed.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.MISMATCH
        assert validation.quote is None


class TestDiscovery:
    async def test_capability_discovery_queries_sources(self) -> None:
        http = http_returning({"sources": []})
        await _adapter(http).discover_capabilities()
        assert http.last_request().url.endswith(endpoints.SOURCES_PATH)

    async def test_fee_discovery_returns_nothing_invented(self) -> None:
        assert await _adapter(http_returning({})).discover_fees(f.POLYGON) == ()

    async def test_health_check_degrades_on_failure(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=502, text="{}"))
        health = await _adapter(http).health_check()
        assert health.state is AdapterState.DEGRADED
