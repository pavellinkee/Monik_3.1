"""Unit-тесты адаптера Velora (ParaSwap)."""

from __future__ import annotations

import pytest

from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DataError, ProviderError, UnsupportedError
from monik.infrastructure.http import FakeHttpClient, HttpResponse
from monik.infrastructure.providers import QuoteRequest
from monik.infrastructure.providers.velora import VeloraAdapter, endpoints
from monik.services.observability import FakeClock
from tests import factories as f

from .support import http_returning, provider_config, resource_manager, secret

PRICE_PAYLOAD = {
    "priceRoute": {
        "srcAmount": "100000000",
        "destAmount": "5140000000000000000",
        "gasCost": "195000",
        "side": "SELL",
        "bestRoute": [
            {
                "percent": 60,
                "swaps": [{"swapExchanges": [{"exchange": "QuickSwapV3", "percent": 100}]}],
            },
            {
                "percent": 40,
                "swaps": [{"swapExchanges": [{"exchange": "SushiSwap", "percent": 100}]}],
            },
        ],
    }
}


def _adapter(http: FakeHttpClient, clock: FakeClock | None = None) -> VeloraAdapter:
    active = clock or FakeClock(f.NOW)
    return VeloraAdapter(
        provider_config(ProviderId.VELORA),
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
    async def test_uses_prices_endpoint(self) -> None:
        """Monik не исполняет свопы, поэтому /transactions не вызывается."""
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert http.last_request().url == f"{endpoints.DEFAULT_BASE_URL}{endpoints.PRICES_PATH}"

    async def test_sends_decimals_from_registry(self) -> None:
        """Decimals берутся из метаданных токена, а не из символа (09 §5)."""
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        params = http.last_request().params
        assert params["srcDecimals"] == "6"
        assert params["destDecimals"] == "18"
        assert params["network"] == "137"
        assert params["version"] == endpoints.API_VERSION
        assert params["side"] == "SELL"

    async def test_unsupported_network_is_reported(self) -> None:
        http = http_returning(PRICE_PAYLOAD)
        source = f.Token(
            network_id=f.NetworkId("optimism"),
            address=f.USDT.address,
            symbol="USDT",
            decimals=6,
        )
        target = f.Token(
            network_id=f.NetworkId("optimism"),
            address=f.AAVE.address,
            symbol="AAVE",
            decimals=18,
        )
        with pytest.raises(UnsupportedError):
            await _adapter(http).get_quote(
                _request(
                    network_id=f.NetworkId("optimism"),
                    input_token=source,
                    output_token=target,
                    input_amount=source.amount_from_base_units(1_000_000),
                )
            )
        assert http.call_count == 0


class TestResponseParsing:
    async def test_parses_dest_amount(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.output_amount.raw == 5_140_000_000_000_000_000

    async def test_parses_gas_cost(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.estimated_gas_units == 195_000

    async def test_route_collects_nested_exchanges(self) -> None:
        quote = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        assert quote.route.steps[0].protocol == "QuickSwapV3+SushiSwap"

    async def test_route_order_does_not_change_fingerprint(self) -> None:
        first = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        reordered = {
            "priceRoute": {
                **PRICE_PAYLOAD["priceRoute"],
                "bestRoute": list(reversed(PRICE_PAYLOAD["priceRoute"]["bestRoute"])),  # type: ignore[index]
            }
        }
        second = await _adapter(http_returning(reordered)).get_quote(_request())
        assert first.route.fingerprint == second.route.fingerprint

    async def test_missing_price_route_is_data_error(self) -> None:
        with pytest.raises(DataError, match="priceRoute"):
            await _adapter(http_returning({})).get_quote(_request())

    async def test_missing_dest_amount_is_data_error(self) -> None:
        with pytest.raises(DataError, match="destAmount"):
            await _adapter(http_returning({"priceRoute": {"srcAmount": "100000000"}})).get_quote(
                _request()
            )

    async def test_source_amount_mismatch_is_rejected(self) -> None:
        payload = {"priceRoute": {**PRICE_PAYLOAD["priceRoute"], "srcAmount": "1"}}
        with pytest.raises(DataError, match="different source amount"):
            await _adapter(http_returning(payload)).get_quote(_request())

    async def test_missing_best_route_does_not_invent_steps(self) -> None:
        payload = {"priceRoute": {"destAmount": "1", "srcAmount": "100000000"}}
        quote = await _adapter(http_returning(payload)).get_quote(_request())
        assert quote.route.steps[0].protocol == "velora_aggregate"


class TestFixedRoute:
    async def test_same_route_is_reproduced(self) -> None:
        adapter = _adapter(http_returning(PRICE_PAYLOAD))
        original = await adapter.get_quote(_request())
        validation = await adapter.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.REPRODUCED

    async def test_changed_route_is_mismatch(self) -> None:
        original = await _adapter(http_returning(PRICE_PAYLOAD)).get_quote(_request())
        changed_payload = {
            "priceRoute": {
                **PRICE_PAYLOAD["priceRoute"],
                "bestRoute": [{"swaps": [{"swapExchanges": [{"exchange": "BalancerV2"}]}]}],
            }
        }
        validation = await _adapter(http_returning(changed_payload)).validate_fixed_route(
            _request(fixed_route=original.route)
        )
        assert validation.outcome is RouteValidationOutcome.MISMATCH


class TestDiscovery:
    async def test_capability_discovery_queries_tokens(self) -> None:
        http = http_returning({"tokens": []})
        await _adapter(http).discover_capabilities()
        assert http.last_request().url.endswith("/tokens/137")

    async def test_fee_discovery_returns_nothing_invented(self) -> None:
        assert await _adapter(http_returning({})).discover_fees(f.POLYGON) == ()

    async def test_health_check_degrades_on_failure(self) -> None:
        http = FakeHttpClient([ProviderError("upstream unavailable")] * 5)
        health = await _adapter(http).health_check()
        assert health.state is AdapterState.DEGRADED

    async def test_partner_header_is_sent_when_configured(self) -> None:
        http = http_returning(PRICE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert "X-Partner" in http.last_request().headers

    async def test_works_without_credentials(self) -> None:
        """Market API не требует ключа для котировок."""
        active = FakeClock(f.NOW)
        adapter = VeloraAdapter(
            provider_config(ProviderId.VELORA),
            http=http_returning(PRICE_PAYLOAD),
            resources=resource_manager(active),
            clock=active,
        )
        quote = await adapter.get_quote(_request())
        assert quote.output_amount.raw > 0


class TestHttpStatuses:
    async def test_server_error_is_provider_error(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=500, text="{}"))
        with pytest.raises(ProviderError):
            await _adapter(http).get_quote(_request())
