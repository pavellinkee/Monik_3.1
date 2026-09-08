"""Provider Registry."""

from __future__ import annotations

from monik.config.root import Configuration
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ConfigurationError
from monik.domain.models.provider import Provider
from monik.domain.value_objects.identity import NetworkId

__all__ = ["ProviderRegistry"]


class ProviderRegistry:
    """Реестр подключённых провайдеров (``08_CAPABILITY_REGISTRY.md`` §22-23).

    Registry отражает то, что **разрешено конфигурацией**. Фактическая
    поддержка операции определяется Capability Registry
    (``17_CONFIGURATION.md`` §66-67), а работоспособность — Health Monitoring.
    """

    def __init__(self, configuration: Configuration) -> None:
        self._providers = {
            provider.provider_id: Provider(
                provider_id=provider.provider_id,
                name=provider.provider_id.value,
                enabled=provider.enabled,
            )
            for provider in configuration.providers
        }
        self._networks = {
            provider.provider_id: set(provider.supported_networks)
            for provider in configuration.providers
        }
        self._pairs = configuration.provider_pairs()

    def get(self, provider_id: ProviderId) -> Provider | None:
        """Найти провайдера."""
        return self._providers.get(provider_id)

    def require(self, provider_id: ProviderId) -> Provider:
        """Найти провайдера или сообщить об ошибке конфигурации."""
        provider = self.get(provider_id)
        if provider is None:
            raise ConfigurationError(
                f"provider {provider_id.value} is not configured",
                code="provider_unknown",
            )
        return provider

    def is_enabled(self, provider_id: ProviderId) -> bool:
        """Включён ли провайдер.

        Disabled провайдер не получает запросов
        (``17_CONFIGURATION.md`` §27).
        """
        provider = self.get(provider_id)
        return provider is not None and provider.enabled

    def enabled(self) -> tuple[Provider, ...]:
        """Все включённые провайдеры."""
        return tuple(provider for provider in self._providers.values() if provider.enabled)

    def declares_network(self, provider_id: ProviderId, network_id: NetworkId) -> bool:
        """Объявляет ли провайдер поддержку сети в конфигурации.

        Это не подтверждение поддержки: оно приходит из Capability Registry
        (``06_AGGREGATOR_ADAPTERS.md`` §15).
        """
        return network_id in self._networks.get(provider_id, set())

    def pairs(self) -> tuple[tuple[ProviderId, ProviderId], ...]:
        """Допустимые пары «BUY провайдер — SELL провайдер»."""
        return self._pairs
