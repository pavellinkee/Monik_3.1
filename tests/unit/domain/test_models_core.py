"""Тесты базовых доменных моделей: сеть, токен, маршрут, котировка."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from monik.domain.enums import OperationType, ProviderId, QuoteStatus, RoutingMode
from monik.domain.models import Quote, Route, RouteStep, Token
from monik.domain.value_objects import NetworkId
from tests import factories as f


class TestToken:
    def test_identity_is_network_plus_address(self) -> None:
        """Canonical identity — network + address (36 §10)."""
        assert f.USDT.key.network_id == f.POLYGON
        assert f.USDT.key.address == f.USDT.address

    def test_symbol_is_not_identity(self) -> None:
        """Одинаковый символ в разных сетях — разные токены (01 §9)."""
        other_network = Token(
            network_id=NetworkId("ethereum"),
            address=f.USDT.address,
            symbol="USDT",
            decimals=6,
        )
        assert other_network.symbol == f.USDT.symbol
        assert other_network.key != f.USDT.key
        assert not other_network.same_as(f.USDT)

    def test_same_token_different_address_case_is_equal(self) -> None:
        upper = Token(
            network_id=f.POLYGON,
            address=str(f.USDT.address).upper().replace("0X", "0x"),
            symbol="USDT",
            decimals=6,
        )
        assert upper.key == f.USDT.key

    def test_decimals_are_explicit_not_derived_from_symbol(self) -> None:
        """Decimals задаются явно (01 §10)."""
        assert f.USDT.decimals == 6
        assert f.AAVE.decimals == 18
        assert f.USDT.amount_from_decimal("1").raw == 1_000_000
        assert f.AAVE.amount_from_decimal("1").raw == 10**18

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Token(network_id=f.POLYGON, address=f.USDT.address, symbol="USDT")  # type: ignore[call-arg]

    def test_rejects_unknown_fields(self) -> None:
        """Provider-specific поля не протекают в domain (36 §99.12)."""
        with pytest.raises(ValidationError):
            Token(
                network_id=f.POLYGON,
                address=f.USDT.address,
                symbol="USDT",
                decimals=6,
                oneinch_internal_id=42,  # type: ignore[call-arg]
            )


class TestRoute:
    def test_fingerprint_is_deterministic(self) -> None:
        assert f.route().fingerprint == f.route().fingerprint

    def test_routing_mode_changes_fingerprint(self) -> None:
        """Routing mode — часть identity маршрута (06 §26)."""
        classic = f.route(routing_mode=RoutingMode.CLASSIC)
        v3 = f.route(routing_mode=RoutingMode.UNISWAP_V3)
        assert classic.fingerprint != v3.fingerprint

    def test_provider_changes_fingerprint(self) -> None:
        assert f.route(provider_id=ProviderId.ONEINCH).fingerprint != (
            f.route(provider_id=ProviderId.ZERO_X).fingerprint
        )

    def test_step_change_changes_fingerprint(self) -> None:
        base = f.route()
        other = f.route(protocol="sushiswap_v2")
        assert base.fingerprint != other.fingerprint

    def test_provider_parameter_order_does_not_matter(self) -> None:
        left = f.route().replace(provider_parameters=(("a", "1"), ("b", "2")))
        right = f.route().replace(provider_parameters=(("b", "2"), ("a", "1")))
        assert left.fingerprint == right.fingerprint

    def test_matches_compares_fingerprints(self) -> None:
        assert f.route().matches(f.route())
        assert not f.route().matches(f.route(routing_mode=RoutingMode.UNISWAP_V3))

    def test_rejects_identical_input_and_output(self) -> None:
        with pytest.raises(ValidationError, match="must differ"):
            f.route(input_token=f.USDT.key, output_token=f.USDT.key)

    def test_rejects_disconnected_steps(self) -> None:
        with pytest.raises(ValidationError, match="not connected"):
            Route(
                provider_id=ProviderId.ONEINCH,
                network_id=f.POLYGON,
                operation=OperationType.BUY,
                routing_mode=RoutingMode.CLASSIC,
                input_token=f.USDT.key,
                output_token=f.AAVE.key,
                steps=(
                    RouteStep(input_token=f.USDT.key, output_token=f.WMATIC.key, protocol="a"),
                    RouteStep(input_token=f.AAVE.key, output_token=f.AAVE.key, protocol="b"),
                ),
            )

    def test_rejects_step_not_starting_at_input(self) -> None:
        with pytest.raises(ValidationError, match="first route step"):
            Route(
                provider_id=ProviderId.ONEINCH,
                network_id=f.POLYGON,
                operation=OperationType.BUY,
                routing_mode=RoutingMode.CLASSIC,
                input_token=f.USDT.key,
                output_token=f.AAVE.key,
                steps=(RouteStep(input_token=f.WMATIC.key, output_token=f.AAVE.key, protocol="a"),),
            )

    def test_rejects_cross_network_token(self) -> None:
        foreign = Token(
            network_id=NetworkId("ethereum"),
            address=f.AAVE.address,
            symbol="AAVE",
            decimals=18,
        )
        with pytest.raises(ValidationError, match="different network"):
            f.route(output_token=foreign.key)

    def test_multi_step_route_is_accepted(self) -> None:
        route = Route(
            provider_id=ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=OperationType.BUY,
            routing_mode=RoutingMode.CLASSIC,
            input_token=f.USDT.key,
            output_token=f.AAVE.key,
            steps=(
                RouteStep(input_token=f.USDT.key, output_token=f.WMATIC.key, protocol="a"),
                RouteStep(input_token=f.WMATIC.key, output_token=f.AAVE.key, protocol="b"),
            ),
        )
        assert len(route.steps) == 2


class TestQuote:
    def test_valid_quote_is_consistent(self) -> None:
        quote = f.quote()
        assert quote.has_usable_output
        assert quote.route.fingerprint == quote.route.fingerprint

    def test_rejects_route_from_another_provider(self) -> None:
        quote = f.quote()
        with pytest.raises(ValidationError, match="route provider"):
            quote.replace(provider_id=ProviderId.VELORA.value)

    def test_rejects_expiry_before_creation(self) -> None:
        quote = f.quote()
        with pytest.raises(ValidationError, match="expires_at"):
            quote.replace(expires_at=quote.created_at - timedelta(seconds=1))

    def test_zero_output_is_not_usable(self) -> None:
        """Нулевой output не является прибыльной возможностью (02 §25)."""
        quote = f.quote(output_raw=0)
        assert not quote.has_usable_output

    def test_freshness_respects_max_age(self) -> None:
        quote = f.quote()
        now = f.NOW + timedelta(seconds=30)
        assert quote.is_fresh(now, timedelta(seconds=60))
        assert not quote.is_fresh(now, timedelta(seconds=10))

    def test_freshness_respects_explicit_expiry(self) -> None:
        quote = f.quote().replace(expires_at=f.NOW + timedelta(seconds=5))
        assert not quote.is_fresh(f.NOW + timedelta(seconds=6), timedelta(hours=1))

    def test_invalid_quote_is_never_fresh(self) -> None:
        """Invalid quote не участвует в сравнении (02 §24)."""
        quote = f.quote().replace(status=QuoteStatus.INVALID.value)
        assert not quote.is_fresh(f.NOW, timedelta(hours=1))

    def test_implied_rate_uses_exact_arithmetic(self) -> None:
        quote = f.quote(input_raw=100_000_000, output_raw=5_000_000_000_000_000_000)
        assert quote.implied_rate == Decimal("0.05")

    def test_is_immutable(self) -> None:
        quote = f.quote()
        with pytest.raises(ValidationError):
            quote.status = QuoteStatus.INVALID  # type: ignore[misc]

    def test_rejects_cross_network_route(self) -> None:
        with pytest.raises(ValidationError):
            Quote(
                provider_id=ProviderId.ONEINCH,
                network_id=NetworkId("ethereum"),
                operation=OperationType.BUY,
                input_token=f.USDT.key,
                output_token=f.AAVE.key,
                input_amount=f.USDT.amount_from_base_units(1),
                output_amount=f.AAVE.amount_from_base_units(1),
                route=f.route(),
                created_at=f.NOW,
                request_id=f.quote().request_id,
            )
