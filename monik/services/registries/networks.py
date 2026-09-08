"""Network Registry."""

from __future__ import annotations

from monik.config.root import Configuration
from monik.domain.errors import ConfigurationError
from monik.domain.models.network import Network
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId

__all__ = ["NetworkRegistry"]


class NetworkRegistry:
    """Authoritative источник информации о сетях (``38_INTERFACES.md`` §26).

    Сеть не зашита в scanner logic: набор приходит из конфигурации
    (``01_PROJECT_REQUIREMENTS.md`` §6).
    """

    def __init__(self, configuration: Configuration) -> None:
        self._networks = {
            network.network_id: Network(
                network_id=network.network_id,
                name=network.name,
                chain_id=network.chain_id,
                native_token_symbol=network.native_token_symbol,
                native_token_decimals=network.native_token_decimals,
                wrapped_native_address=network.wrapped_native_address,
                enabled=network.enabled,
            )
            for network in configuration.networks
        }
        self._rpc_urls = {network.network_id: network.rpc_url for network in configuration.networks}

    def get(self, network_id: NetworkId) -> Network | None:
        """Найти сеть по идентификатору."""
        return self._networks.get(network_id)

    def require(self, network_id: NetworkId) -> Network:
        """Найти сеть или сообщить об ошибке конфигурации."""
        network = self.get(network_id)
        if network is None:
            raise ConfigurationError(
                f"network {network_id} is not configured", code="network_unknown"
            )
        return network

    def is_enabled(self, network_id: NetworkId) -> bool:
        """Включена ли сеть.

        Disabled сеть не участвует в сканировании
        (``02_LEVEL1_SCANNER.md`` §72).
        """
        network = self.get(network_id)
        return network is not None and network.enabled

    def enabled(self) -> tuple[Network, ...]:
        """Все включённые сети."""
        return tuple(network for network in self._networks.values() if network.enabled)

    def rpc_url(self, network_id: NetworkId) -> str | None:
        """RPC endpoint сети, если он задан."""
        return self._rpc_urls.get(network_id)

    def wrapped_native_token(self, network_id: NetworkId) -> TokenKey:
        """Canonical identity обёрнутого native token сети.

        Native asset идентифицируется через canonical Token identity, а не
        по символу (``36_DATA_MODELS.md`` §11).
        """
        network = self.require(network_id)
        return TokenKey(network_id=network.network_id, address=network.wrapped_native_address)
