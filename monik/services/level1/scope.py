"""Определение границ одного цикла Level 1.

Scope полностью определяется конфигурацией и реестрами
(``02_LEVEL1_SCANNER.md`` §5, §68): списки сетей, токенов, сумм и
провайдеров в коде не зашиты. Изменение конфигурации применяется со
следующего цикла (``02_LEVEL1_SCANNER.md`` §69), поэтому scope
фиксируется на старте.
"""

from __future__ import annotations

from monik.config.root import Configuration
from monik.domain.errors import ConfigurationError
from monik.domain.models.scan import ScanScope
from monik.domain.models.token import Token
from monik.services.registries.networks import NetworkRegistry
from monik.services.registries.providers import ProviderRegistry
from monik.services.registries.tokens import TokenRegistry

__all__ = ["ScopeBuilder"]


class ScopeBuilder:
    """Строит :class:`ScanScope` из актуальной конфигурации."""

    def __init__(
        self,
        configuration: Configuration,
        *,
        networks: NetworkRegistry,
        tokens: TokenRegistry,
        providers: ProviderRegistry,
    ) -> None:
        self._configuration = configuration
        self._networks = networks
        self._tokens = tokens
        self._providers = providers

    def build(self) -> ScanScope:
        """Собрать scope цикла.

        Отключённые сети, токены и провайдеры в scope не попадают
        (``02_LEVEL1_SCANNER.md`` §70-72).
        """
        scanner = self._configuration.scanner
        network_id = scanner.base_network
        if not self._networks.is_enabled(network_id):
            raise ConfigurationError(
                f"base network {network_id} is disabled; Level 1 has nothing to scan"
            )

        base_token = self._tokens.base_token
        providers = tuple(
            provider.provider_id
            for provider in self._providers.enabled()
            if self._providers.declares_network(provider.provider_id, network_id)
        )
        if not providers:
            raise ConfigurationError(
                f"no enabled provider declares network {network_id}; Level 1 has no source"
            )

        tokens = self.scan_tokens()
        if not tokens:
            raise ConfigurationError("no enabled intermediate token is available for scanning")

        raw_amounts = tuple(
            base_token.amount_from_decimal(str(amount)).raw for amount in scanner.amounts
        )
        return ScanScope(
            networks=(network_id,),
            providers=providers,
            tokens=tuple(token.key for token in tokens),
            raw_amounts=raw_amounts,
        )

    def scan_tokens(self) -> tuple[Token, ...]:
        """Промежуточные токены цикла, ограниченные Top-N (§6)."""
        limit = self._configuration.scanner.level1.top_tokens
        return self._tokens.scan_tokens()[:limit]

    @property
    def base_token(self) -> Token:
        """Базовый токен: вход и выход round-trip (``10_LEVEL_1_SCANNER.md`` §37)."""
        return self._tokens.base_token
