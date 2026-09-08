"""Тесты Network, Token и Provider registries."""

from __future__ import annotations

import copy

import pytest

from monik.config import Configuration, parse_configuration
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ConfigurationError
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId, TokenAddress
from monik.services.registries import NetworkRegistry, ProviderRegistry, TokenRegistry
from tests.unit.config.conftest import USDT_ADDRESS, VALID_ENV

from .conftest import registry_document

POLYGON = NetworkId("polygon")
AAVE_ADDRESS = "0xD6DF932A45C0f255f85145f286eA0b292B21C90B"


class TestNetworkRegistry:
    def test_returns_configured_network(self, configuration: Configuration) -> None:
        registry = NetworkRegistry(configuration)
        network = registry.require(POLYGON)
        assert network.chain_id == 137
        assert network.enabled

    def test_unknown_network_is_reported(self, configuration: Configuration) -> None:
        registry = NetworkRegistry(configuration)
        assert registry.get(NetworkId("arbitrum")) is None
        with pytest.raises(ConfigurationError, match="not configured"):
            registry.require(NetworkId("arbitrum"))

    def test_enabled_filter(self, configuration: Configuration) -> None:
        registry = NetworkRegistry(configuration)
        assert [network.network_id for network in registry.enabled()] == [POLYGON]
        assert registry.is_enabled(POLYGON)
        assert not registry.is_enabled(NetworkId("arbitrum"))

    def test_wrapped_native_token_identity(self, configuration: Configuration) -> None:
        """Native asset идентифицируется canonical identity, не символом (36 §11)."""
        registry = NetworkRegistry(configuration)
        key = registry.wrapped_native_token(POLYGON)
        assert key.network_id == POLYGON
        assert key.address.startswith("0x")


class TestTokenRegistry:
    def test_lookup_by_canonical_identity(self, configuration: Configuration) -> None:
        registry = TokenRegistry(configuration)
        token = registry.require(TokenKey(network_id=POLYGON, address=TokenAddress(USDT_ADDRESS)))
        assert token.symbol == "USDT"
        assert token.decimals == 6

    def test_address_case_does_not_matter(self, configuration: Configuration) -> None:
        registry = TokenRegistry(configuration)
        upper = registry.get_by_address(POLYGON, USDT_ADDRESS.upper().replace("0X", "0x"))
        assert upper is not None
        assert upper.symbol == "USDT"

    def test_symbol_is_not_identity(self, configuration: Configuration) -> None:
        """Поиск по символу возвращает набор, а не единственный токен (36 §10)."""
        registry = TokenRegistry(configuration)
        found = registry.find_by_symbol(POLYGON, "usdt")
        assert len(found) == 1
        assert registry.find_by_symbol(NetworkId("arbitrum"), "USDT") == ()

    def test_decimals_come_from_registry(self, configuration: Configuration) -> None:
        """Decimals не выводятся из символа (09 §5)."""
        registry = TokenRegistry(configuration)
        assert registry.decimals(TokenKey(network_id=POLYGON, address=USDT_ADDRESS)) == 6
        assert registry.decimals(TokenKey(network_id=POLYGON, address=AAVE_ADDRESS)) == 18

    def test_unknown_token_is_reported(self, configuration: Configuration) -> None:
        registry = TokenRegistry(configuration)
        missing = TokenKey(network_id=POLYGON, address="0x0000000000000000000000000000000000000001")
        assert not registry.exists(missing)
        with pytest.raises(ConfigurationError, match="not configured"):
            registry.require(missing)

    def test_disabled_tokens_are_excluded(self, configuration: Configuration) -> None:
        """Disabled токен не сканируется (02 §70)."""
        registry = TokenRegistry(configuration)
        symbols = [token.symbol for token in registry.list_enabled(POLYGON)]
        assert "LINK" not in symbols

    def test_scan_tokens_exclude_base_token(self, configuration: Configuration) -> None:
        registry = TokenRegistry(configuration)
        assert registry.base_token.symbol == "USDT"
        assert all(token.symbol != "USDT" for token in registry.scan_tokens())

    def test_scan_tokens_are_ordered_by_rank(self, configuration: Configuration) -> None:
        registry = TokenRegistry(configuration)
        assert [token.symbol for token in registry.scan_tokens()] == ["AAVE", "WETH"]

    def test_scan_tokens_respect_top_n(self) -> None:
        """Ограничение Top-N (01 §7)."""
        document = registry_document()
        document["scanner"]["level1"] = {"top_tokens": 1}
        config = parse_configuration(document, environ=dict(VALID_ENV)).config
        registry = TokenRegistry(config)
        assert [token.symbol for token in registry.scan_tokens()] == ["AAVE"]

    def test_registry_has_no_hardcoded_tokens(self) -> None:
        """Собственного списка токенов у реестра нет (10 §4)."""
        document = copy.deepcopy(registry_document())
        document["tokens"] = [
            token for token in document["tokens"] if token["symbol"] in {"USDT", "AAVE"}
        ]
        config = parse_configuration(document, environ=dict(VALID_ENV)).config
        registry = TokenRegistry(config)
        assert {token.symbol for token in registry.list_enabled()} == {"USDT", "AAVE"}


class TestProviderRegistry:
    def test_enabled_providers(self, configuration: Configuration) -> None:
        registry = ProviderRegistry(configuration)
        assert {provider.provider_id for provider in registry.enabled()} == {
            ProviderId.ONEINCH,
            ProviderId.ZERO_X,
        }

    def test_disabled_provider_is_reported(self, configuration: Configuration) -> None:
        registry = ProviderRegistry(configuration)
        assert not registry.is_enabled(ProviderId.VELORA)
        assert registry.get(ProviderId.VELORA) is None

    def test_unknown_provider_is_reported(self, configuration: Configuration) -> None:
        registry = ProviderRegistry(configuration)
        with pytest.raises(ConfigurationError, match="not configured"):
            registry.require(ProviderId.UNISWAP)

    def test_declared_networks(self, configuration: Configuration) -> None:
        """Объявление сети не является подтверждением поддержки (06 §15)."""
        registry = ProviderRegistry(configuration)
        assert registry.declares_network(ProviderId.ONEINCH, POLYGON)
        assert not registry.declares_network(ProviderId.ONEINCH, NetworkId("arbitrum"))

    def test_pairs_are_cross_provider(self, configuration: Configuration) -> None:
        registry = ProviderRegistry(configuration)
        pairs = registry.pairs()
        assert (ProviderId.ONEINCH, ProviderId.ZERO_X) in pairs
        assert all(buy is not sell for buy, sell in pairs)
