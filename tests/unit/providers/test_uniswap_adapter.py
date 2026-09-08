"""Unit-тесты адаптера Uniswap."""

from __future__ import annotations

import pytest

from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import (
    OperationType,
    RouteValidationOutcome,
    RoutingMode,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DataError, ProviderError, UnsupportedError
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.infrastructure.providers import QuoteRequest
from monik.infrastructure.providers.uniswap import UniswapAdapter, endpoints
from monik.services.observability import FakeClock
from tests import factories as f

from .support import http_returning, provider_config, resource_manager, secret

CLASSIC_PAYLOAD = {
    "routing": "CLASSIC",
    "quote": {
        "output": {"amount": "5140000000000000000"},
        "gasUseEstimate": "230000",
        "route": [
            [
                {"type": "v3-pool", "address": "0xpool1", "fee": "500"},
                {"type": "v3-pool", "address": "0xpool2", "fee": "3000"},
            ]
        ],
    },
}

DUTCH_PAYLOAD = {
    "routing": "DUTCH_V2",
    "quote": {"output": {"amount": "5150000000000000000"}},
}


def _adapter(http: FakeHttpClient, clock: FakeClock | None = None) -> UniswapAdapter:
    active = clock or FakeClock(f.NOW)
    return UniswapAdapter(
        provider_config(ProviderId.UNISWAP),
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
    async def test_uses_post_with_documented_body(self) -> None:
        http = http_returning(CLASSIC_PAYLOAD)
        await _adapter(http).get_quote(_request())
        sent = http.last_request()
        assert sent.method == "POST"
        assert sent.url == f"{endpoints.DEFAULT_BASE_URL}{endpoints.QUOTE_PATH}"
        assert sent.json_body["type"] == "EXACT_INPUT"
        assert sent.json_body["tokenIn"] == str(f.USDT.address)
        assert sent.json_body["tokenOutChainId"] == 137
        assert sent.json_body["amount"] == "100000000"

    async def test_sends_api_key_header(self) -> None:
        http = http_returning(CLASSIC_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert http.last_request().headers[endpoints.API_KEY_HEADER]

    async def test_defaults_to_classic_routing_preference(self) -> None:
        """Адаптер не выбирает UniswapX самостоятельно."""
        http = http_returning(CLASSIC_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert http.last_request().json_body["routingPreference"] == "CLASSIC"

    async def test_uniswapx_preference_is_requested_when_asked(self) -> None:
        http = http_returning(DUTCH_PAYLOAD)
        await _adapter(http).get_quote(_request(routing_mode=RoutingMode.UNISWAPX_DUTCH_V2))
        assert http.last_request().json_body["routingPreference"] == "UNISWAPX"

    async def test_unsupported_network_is_reported(self) -> None:
        http = http_returning(CLASSIC_PAYLOAD)
        source = f.Token(
            network_id=f.NetworkId("celo"), address=f.USDT.address, symbol="USDT", decimals=6
        )
        target = f.Token(
            network_id=f.NetworkId("celo"), address=f.AAVE.address, symbol="AAVE", decimals=18
        )
        with pytest.raises(UnsupportedError):
            await _adapter(http).get_quote(
                _request(
                    network_id=f.NetworkId("celo"),
                    input_token=source,
                    output_token=target,
                    input_amount=source.amount_from_base_units(1_000_000),
                )
            )
        assert http.call_count == 0


class TestRoutingModes:
    async def test_classic_routing_is_preserved(self) -> None:
        quote = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        assert quote.route.routing_mode is RoutingMode.CLASSIC

    async def test_uniswapx_routing_is_preserved(self) -> None:
        """Classic и UniswapX не объединяются (06 §27)."""
        quote = await _adapter(http_returning(DUTCH_PAYLOAD)).get_quote(_request())
        assert quote.route.routing_mode is RoutingMode.UNISWAPX_DUTCH_V2

    async def test_routing_mode_changes_route_identity(self) -> None:
        """Routing mode — часть identity маршрута (06 §26)."""
        classic = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        same_pools_dutch = {
            "routing": "DUTCH_V2",
            "quote": CLASSIC_PAYLOAD["quote"],
        }
        dutch = await _adapter(http_returning(same_pools_dutch)).get_quote(_request())
        assert classic.route.fingerprint != dutch.route.fingerprint

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("CLASSIC", RoutingMode.CLASSIC),
            ("DUTCH_V2", RoutingMode.UNISWAPX_DUTCH_V2),
            ("DUTCH_V3", RoutingMode.UNISWAPX_DUTCH_V3),
            ("PRIORITY", RoutingMode.UNISWAPX_PRIORITY),
        ],
    )
    async def test_known_routing_values_are_mapped(self, raw: str, expected: RoutingMode) -> None:
        payload = {"routing": raw, "quote": {"output": {"amount": "1"}}}
        quote = await _adapter(http_returning(payload)).get_quote(_request())
        assert quote.route.routing_mode is expected

    async def test_unknown_routing_mode_is_rejected(self) -> None:
        """Фиктивный режим не создаётся (06 §26)."""
        payload = {"routing": "SOMETHING_NEW", "quote": {"output": {"amount": "1"}}}
        with pytest.raises(DataError, match="unknown routing mode"):
            await _adapter(http_returning(payload)).get_quote(_request())

    async def test_missing_routing_is_rejected(self) -> None:
        with pytest.raises(DataError, match="routing"):
            await _adapter(http_returning({"quote": {"output": {"amount": "1"}}})).get_quote(
                _request()
            )


class TestResponseParsing:
    async def test_parses_output_amount(self) -> None:
        quote = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        assert quote.output_amount.raw == 5_140_000_000_000_000_000

    async def test_parses_gas_estimate(self) -> None:
        quote = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        assert quote.estimated_gas_units == 230_000

    async def test_route_records_pools(self) -> None:
        quote = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        assert "v3-pool:0xpool1" in quote.route.steps[0].protocol
        assert "v3-pool:0xpool2" in quote.route.steps[0].protocol

    async def test_pool_order_does_not_change_fingerprint(self) -> None:
        reordered = {
            "routing": "CLASSIC",
            "quote": {
                **CLASSIC_PAYLOAD["quote"],
                "route": [list(reversed(CLASSIC_PAYLOAD["quote"]["route"][0]))],  # type: ignore[index]
            },
        }
        first = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        second = await _adapter(http_returning(reordered)).get_quote(_request())
        assert first.route.fingerprint == second.route.fingerprint

    async def test_uniswapx_without_pools_does_not_invent_steps(self) -> None:
        quote = await _adapter(http_returning(DUTCH_PAYLOAD)).get_quote(_request())
        assert quote.route.steps[0].protocol == "uniswap_aggregate"

    async def test_float_amount_is_rejected(self) -> None:
        payload = {"routing": "CLASSIC", "quote": {"output": {"amount": 5.1}}}
        with pytest.raises(DataError, match="non-integer amount"):
            await _adapter(http_returning(payload)).get_quote(_request())

    async def test_missing_quote_is_rejected(self) -> None:
        with pytest.raises(DataError, match="quote"):
            await _adapter(http_returning({"routing": "CLASSIC"})).get_quote(_request())


class TestFixedRoute:
    async def test_same_route_is_reproduced(self) -> None:
        adapter = _adapter(http_returning(CLASSIC_PAYLOAD))
        original = await adapter.get_quote(_request())
        validation = await adapter.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.REPRODUCED

    async def test_routing_mode_change_is_mismatch(self) -> None:
        """Смена режима маршрутизации не считается тем же маршрутом."""
        original = await _adapter(http_returning(CLASSIC_PAYLOAD)).get_quote(_request())
        switched = {"routing": "DUTCH_V2", "quote": CLASSIC_PAYLOAD["quote"]}
        validation = await _adapter(http_returning(switched)).validate_fixed_route(
            _request(fixed_route=original.route)
        )
        assert validation.outcome is RouteValidationOutcome.MISMATCH
        assert validation.quote is None


class TestDiscovery:
    def test_declares_all_routing_modes(self) -> None:
        capabilities = _adapter(http_returning(CLASSIC_PAYLOAD)).capabilities
        assert RoutingMode.CLASSIC in capabilities.routing_modes
        assert RoutingMode.UNISWAPX_DUTCH_V2 in capabilities.routing_modes
        assert RoutingMode.UNISWAPX_PRIORITY in capabilities.routing_modes

    async def test_fee_discovery_returns_nothing_invented(self) -> None:
        assert await _adapter(http_returning({})).discover_fees(f.POLYGON) == ()

    async def test_health_check_degrades_on_failure(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=500, text="{}"))
        health = await _adapter(http).health_check()
        assert health.state is AdapterState.DEGRADED

    async def test_server_error_is_provider_error(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=503, text="{}"))
        with pytest.raises(ProviderError):
            await _adapter(http).get_quote(_request())
