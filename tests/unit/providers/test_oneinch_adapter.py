"""Unit-тесты адаптера 1inch."""

from __future__ import annotations

from decimal import Decimal

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
from monik.infrastructure.providers.oneinch import OneInchAdapter, endpoints
from monik.services.observability import FakeClock
from tests import factories as f

from .support import http_returning, provider_config, resource_manager, secret

QUOTE_PAYLOAD = {
    "dstAmount": "5140000000000000000",
    "gas": 210000,
    "protocols": [[[{"name": "QUICKSWAP_V3", "part": 100}]]],
}


def _adapter(http: FakeHttpClient, clock: FakeClock | None = None) -> OneInchAdapter:
    active_clock = clock or FakeClock(f.NOW)
    return OneInchAdapter(
        provider_config(ProviderId.ONEINCH),
        http=http,
        resources=resource_manager(active_clock),
        clock=active_clock,
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
    async def test_targets_documented_endpoint(self) -> None:
        http = http_returning(QUOTE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        url = http.last_request().url
        assert url == f"{endpoints.DEFAULT_BASE_URL}/swap/{endpoints.API_VERSION}/137/quote"

    async def test_sends_documented_parameters(self) -> None:
        http = http_returning(QUOTE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        params = http.last_request().params
        assert params["src"] == str(f.USDT.address)
        assert params["dst"] == str(f.AAVE.address)
        assert params["amount"] == "100000000"

    async def test_sends_bearer_credentials(self) -> None:
        http = http_returning(QUOTE_PAYLOAD)
        await _adapter(http).get_quote(_request())
        assert http.last_request().headers["Authorization"].startswith("Bearer ")

    async def test_unsupported_network_is_reported(self) -> None:
        http = http_returning(QUOTE_PAYLOAD)
        foreign = f.Token(
            network_id=f.NetworkId("arbitrum"),
            address=f.USDT.address,
            symbol="USDT",
            decimals=6,
        )
        other = f.Token(
            network_id=f.NetworkId("arbitrum"),
            address=f.AAVE.address,
            symbol="AAVE",
            decimals=18,
        )
        with pytest.raises(UnsupportedError, match="does not support network"):
            await _adapter(http).get_quote(
                _request(
                    network_id=f.NetworkId("arbitrum"),
                    input_token=foreign,
                    output_token=other,
                    input_amount=foreign.amount_from_base_units(1_000_000),
                )
            )
        assert http.call_count == 0


class TestResponseParsing:
    async def test_parses_output_amount(self) -> None:
        quote = await _adapter(http_returning(QUOTE_PAYLOAD)).get_quote(_request())
        assert quote.output_amount.raw == 5_140_000_000_000_000_000
        assert quote.output_amount.as_decimal == Decimal("5.140000000000000000")

    async def test_parses_gas_estimate(self) -> None:
        quote = await _adapter(http_returning(QUOTE_PAYLOAD)).get_quote(_request())
        assert quote.estimated_gas_units == 210_000

    async def test_route_records_liquidity_sources(self) -> None:
        quote = await _adapter(http_returning(QUOTE_PAYLOAD)).get_quote(_request())
        assert quote.route.steps[0].protocol == "QUICKSWAP_V3"

    async def test_route_is_deterministic_regardless_of_protocol_order(self) -> None:
        """Отпечаток не зависит от порядка элементов в JSON (06 §83)."""
        first = await _adapter(
            http_returning(
                {
                    **QUOTE_PAYLOAD,
                    "protocols": [[[{"name": "A"}, {"name": "B"}]]],
                }
            )
        ).get_quote(_request())
        second = await _adapter(
            http_returning(
                {
                    **QUOTE_PAYLOAD,
                    "protocols": [[[{"name": "B"}, {"name": "A"}]]],
                }
            )
        ).get_quote(_request())
        assert first.route.fingerprint == second.route.fingerprint

    async def test_missing_protocols_do_not_invent_steps(self) -> None:
        payload = {"dstAmount": "1", "gas": 1}
        quote = await _adapter(http_returning(payload)).get_quote(_request())
        assert len(quote.route.steps) == 1
        assert quote.route.steps[0].protocol == "1inch_aggregate"

    async def test_output_is_marked_fee_inclusive(self) -> None:
        """Комиссия, включённая в ответ, не вычитается повторно (01 §29)."""
        quote = await _adapter(http_returning(QUOTE_PAYLOAD)).get_quote(_request())
        assert quote.raw_output_amount_includes_fees is True

    async def test_missing_required_field_is_data_error(self) -> None:
        with pytest.raises(DataError, match="dstAmount"):
            await _adapter(http_returning({"gas": 1})).get_quote(_request())

    async def test_float_amount_is_rejected(self) -> None:
        """Float в финансовом поле недопустим (09 §3)."""
        with pytest.raises(DataError, match="non-integer amount"):
            await _adapter(http_returning({"dstAmount": 1.5})).get_quote(_request())

    async def test_malformed_amount_is_rejected(self) -> None:
        with pytest.raises(DataError, match="malformed amount"):
            await _adapter(http_returning({"dstAmount": "not-a-number"})).get_quote(_request())

    async def test_negative_amount_is_rejected(self) -> None:
        with pytest.raises(DataError, match="negative amount"):
            await _adapter(http_returning({"dstAmount": "-5"})).get_quote(_request())

    async def test_non_object_response_is_rejected(self) -> None:
        with pytest.raises(DataError, match="not a JSON object"):
            await _adapter(http_returning(["unexpected"])).get_quote(_request())

    async def test_invalid_json_is_data_error(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=200, text="<html>"))
        with pytest.raises(DataError, match="not valid JSON"):
            await _adapter(http).get_quote(_request())


class TestErrorTranslation:
    async def test_rate_limit_is_normalized(self) -> None:
        http = FakeHttpClient(
            handler=lambda request: HttpResponse(
                status_code=429, text="{}", headers={"retry-after": "12"}
            )
        )
        with pytest.raises(RateLimitError):
            await _adapter(http).get_quote(_request())

    async def test_authentication_error_is_normalized(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=401, text="{}"))
        with pytest.raises(AuthenticationError):
            await _adapter(http).get_quote(_request())

    async def test_server_error_is_provider_error(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=503, text="{}"))
        with pytest.raises(ProviderError):
            await _adapter(http).get_quote(_request())

    async def test_client_error_is_data_error(self) -> None:
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=400, text="{}"))
        with pytest.raises(DataError):
            await _adapter(http).get_quote(_request())


class TestFixedRoute:
    async def test_matching_route_is_reproduced(self) -> None:
        adapter = _adapter(http_returning(QUOTE_PAYLOAD))
        original = await adapter.get_quote(_request())
        validation = await adapter.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.REPRODUCED
        assert validation.quote is not None

    async def test_different_route_is_reported_as_mismatch(self) -> None:
        """Другой маршрут не принимается молча (06 §52)."""
        adapter = _adapter(http_returning(QUOTE_PAYLOAD))
        original = await adapter.get_quote(_request())
        changed = _adapter(
            http_returning({**QUOTE_PAYLOAD, "protocols": [[[{"name": "SUSHISWAP"}]]]})
        )
        validation = await changed.validate_fixed_route(_request(fixed_route=original.route))
        assert validation.outcome is RouteValidationOutcome.MISMATCH
        assert validation.quote is None

    async def test_missing_fixed_route_is_rejected(self) -> None:
        with pytest.raises(DataError, match="requires the route"):
            await _adapter(http_returning(QUOTE_PAYLOAD)).validate_fixed_route(_request())

    def test_fixed_route_support_is_declared_honestly(self) -> None:
        """Адаптер не заявляет возможности, которых у API нет (06 §22)."""
        adapter = _adapter(http_returning(QUOTE_PAYLOAD))
        assert adapter.capabilities.supports_fixed_route is False


class TestDiscovery:
    async def test_fee_discovery_returns_nothing_invented(self) -> None:
        assert await _adapter(http_returning({})).discover_fees(f.POLYGON) == ()

    async def test_capability_discovery_queries_tokens(self) -> None:
        http = http_returning({"tokens": {}})
        await _adapter(http).discover_capabilities()
        assert "tokens" in http.last_request().url

    async def test_health_check_reports_ready(self) -> None:
        health = await _adapter(http_returning({"protocols": []})).health_check()
        assert health.is_usable

    async def test_health_check_reports_degraded_on_failure(self) -> None:
        """Сбой health check не означает отсутствие поддержки (06 §21).

        Провайдер помечается DEGRADED и остаётся пригодным: система
        продолжает работу с доступными провайдерами (01 §38).
        """
        http = FakeHttpClient(handler=lambda request: HttpResponse(status_code=503, text="{}"))
        health = await _adapter(http).health_check()
        assert health.state is AdapterState.DEGRADED
        assert health.detail == "http_server_error"
        assert health.is_usable
