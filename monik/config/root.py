"""Корневая модель конфигурации и её cross-subsystem валидация.

Configuration определяет, **что разрешено**; Capability Registry определяет,
**что фактически поддерживается** (``17_CONFIGURATION.md`` §67). Поэтому
валидация здесь проверяет согласованность настроек между собой, но не
объявляет провайдера доступным (``17_CONFIGURATION.md`` §66).
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.config.sections import (
    ApplicationConfig,
    CapabilityConfig,
    DatabaseConfig,
    FeeConfig,
    GasConfig,
    HealthConfig,
    HttpConfig,
    LoggingConfig,
    MetricsConfig,
    NetworkConfig,
    NotificationConfig,
    PriceConfig,
    ProfitabilityConfig,
    ProviderConfig,
    ResourceConfig,
    RoutePolicyConfig,
    ScannerConfig,
    SchedulerConfig,
    TokenConfig,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.fingerprints import compute_fingerprint
from monik.domain.value_objects.identity import NetworkId

__all__ = ["Configuration"]


class Configuration(ConfigSection):
    """Полная валидированная конфигурация Monik.

    Объект immutable в пределах текущего runtime
    (``17_CONFIGURATION.md`` §50). Секреты в него не входят: они хранятся
    отдельно в ``SecretStore``, поэтому сериализация конфигурации физически
    не может их раскрыть.
    """

    application: ApplicationConfig = ApplicationConfig()
    networks: tuple[NetworkConfig, ...] = Field(min_length=1)
    providers: tuple[ProviderConfig, ...] = Field(min_length=1)
    tokens: tuple[TokenConfig, ...] = Field(min_length=1)
    routes: RoutePolicyConfig = RoutePolicyConfig()
    scanner: ScannerConfig
    profitability: ProfitabilityConfig = ProfitabilityConfig()
    capabilities: CapabilityConfig = CapabilityConfig()
    fees: FeeConfig = FeeConfig()
    gas: GasConfig = GasConfig()
    prices: PriceConfig = PriceConfig()
    http: HttpConfig = HttpConfig()
    resources: ResourceConfig = ResourceConfig()
    health: HealthConfig = HealthConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    notifications: NotificationConfig = NotificationConfig()
    database: DatabaseConfig = DatabaseConfig()
    logging: LoggingConfig = LoggingConfig()
    metrics: MetricsConfig = MetricsConfig()

    # --- уникальность идентификаторов -------------------------------------

    @model_validator(mode="after")
    def _validate_unique_identities(self) -> Self:
        network_ids = [network.network_id for network in self.networks]
        if len(set(network_ids)) != len(network_ids):
            raise ValueError("duplicate network id in configuration")

        provider_ids = [provider.provider_id for provider in self.providers]
        if len(set(provider_ids)) != len(provider_ids):
            raise ValueError("duplicate provider id in configuration")

        token_keys = [(token.network_id, token.address) for token in self.tokens]
        if len(set(token_keys)) != len(token_keys):
            raise ValueError("duplicate token (network, address) in configuration")
        return self

    # --- минимально необходимый набор -------------------------------------

    @model_validator(mode="after")
    def _validate_startup_requirements(self) -> Self:
        """Перед запуском Scanner должен быть непустой рабочий набор.

        Соответствует ``17_CONFIGURATION.md`` §65.
        """
        if not self.enabled_networks:
            raise ValueError("at least one network must be enabled")
        if not self.enabled_providers:
            raise ValueError("at least one provider must be enabled")
        if not self.enabled_tokens:
            raise ValueError("at least one token must be enabled")
        return self

    # --- согласованность между подсистемами --------------------------------

    @model_validator(mode="after")
    def _validate_cross_references(self) -> Self:
        """Проверить связи tokens ↔ networks ↔ providers ↔ routes ↔ amounts.

        Соответствует ``17_CONFIGURATION.md`` §62-63.
        """
        enabled_network_ids = {network.network_id for network in self.enabled_networks}

        for token in self.enabled_tokens:
            if token.network_id not in enabled_network_ids:
                raise ValueError(
                    f"token {token.symbol} references network {token.network_id} "
                    "which is not enabled"
                )

        for provider in self.enabled_providers:
            supported = set(provider.supported_networks)
            if not supported & enabled_network_ids:
                raise ValueError(
                    f"provider {provider.provider_id.value} is enabled but supports none "
                    "of the enabled networks"
                )
            unknown = supported - {network.network_id for network in self.networks}
            if unknown:
                raise ValueError(
                    f"provider {provider.provider_id.value} references unknown networks: "
                    f"{', '.join(sorted(unknown))}"
                )

        enabled_provider_ids = {provider.provider_id for provider in self.enabled_providers}
        for pair in self.routes.allowed_pairs:
            for provider_id in (pair.buy, pair.sell):
                if provider_id not in enabled_provider_ids:
                    raise ValueError(
                        f"route policy references provider {provider_id.value} which is not enabled"
                    )

        if not self.provider_pairs():
            raise ValueError(
                "route policy leaves no usable provider pair; enable more providers "
                "or allow same-provider round trips"
            )
        return self

    @model_validator(mode="after")
    def _validate_scanner_scope(self) -> Self:
        """Базовая сеть, базовый токен и суммы обязаны быть согласованы."""
        base_network = self.network(self.scanner.base_network)
        if base_network is None or not base_network.enabled:
            raise ValueError(
                f"scanner base_network {self.scanner.base_network} is unknown or disabled"
            )
        base_token = self.token(self.scanner.base_network, self.scanner.base_token_address)
        if base_token is None or not base_token.enabled:
            raise ValueError(
                f"scanner base token {self.scanner.base_token_address} is unknown or disabled "
                f"on network {self.scanner.base_network}"
            )

        for amount in self.scanner.amounts:
            try:
                TokenAmount.from_decimal(amount, base_token.decimals)
            except ValueError as exc:
                raise ValueError(
                    f"scanner amount {amount} is not representable with "
                    f"{base_token.decimals} decimals of {base_token.symbol}"
                ) from exc

        tradable = [
            token
            for token in self.enabled_tokens
            if token.network_id == self.scanner.base_network
            and token.address != self.scanner.base_token_address
        ]
        if not tradable:
            raise ValueError(
                "scanner needs at least one enabled token besides the base token "
                f"on network {self.scanner.base_network}"
            )
        return self

    @model_validator(mode="after")
    def _validate_production_safety(self) -> Self:
        """Production не должен запускаться с development-настройками.

        Соответствует ``24_DEPLOYMENT.md`` §65 и ``40_ACCEPTANCE_CRITERIA.md``.
        """
        if not self.application.is_production:
            return self
        if self.logging.level.value == "DEBUG":
            raise ValueError("DEBUG logging is not allowed in production")
        if not self.database.integrity_check_on_startup:
            raise ValueError("integrity_check_on_startup must stay enabled in production")
        for provider in self.enabled_providers:
            if provider.api_key is None:
                raise ValueError(
                    f"provider {provider.provider_id.value} is enabled in production "
                    "without a credentials reference"
                )
        return self

    # --- удобные выборки ---------------------------------------------------

    @property
    def enabled_networks(self) -> tuple[NetworkConfig, ...]:
        """Включённые сети."""
        return tuple(network for network in self.networks if network.enabled)

    @property
    def enabled_providers(self) -> tuple[ProviderConfig, ...]:
        """Включённые провайдеры."""
        return tuple(provider for provider in self.providers if provider.enabled)

    @property
    def enabled_tokens(self) -> tuple[TokenConfig, ...]:
        """Включённые токены."""
        return tuple(token for token in self.tokens if token.enabled)

    def network(self, network_id: NetworkId) -> NetworkConfig | None:
        """Найти сеть по идентификатору."""
        for network in self.networks:
            if network.network_id == network_id:
                return network
        return None

    def provider(self, provider_id: ProviderId) -> ProviderConfig | None:
        """Найти провайдера по идентификатору."""
        for provider in self.providers:
            if provider.provider_id is provider_id:
                return provider
        return None

    def token(self, network_id: NetworkId, address: str) -> TokenConfig | None:
        """Найти токен по canonical identity."""
        for token in self.tokens:
            if token.network_id == network_id and token.address == address:
                return token
        return None

    def provider_pairs(self) -> tuple[tuple[ProviderId, ProviderId], ...]:
        """Все допустимые пары «BUY провайдер — SELL провайдер».

        Учитывает enabled-состояние, политику маршрутов и запрет
        одинакового провайдера с обеих сторон, если он не разрешён
        (``02_LEVEL1_SCANNER.md`` §18).
        """
        pairs: list[tuple[ProviderId, ProviderId]] = []
        for buy in self.enabled_providers:
            for sell in self.enabled_providers:
                if buy.provider_id is sell.provider_id and not (
                    self.routes.allow_same_provider and buy.allow_same_provider_round_trip
                ):
                    continue
                if not self.routes.is_allowed(buy.provider_id, sell.provider_id):
                    continue
                pairs.append((buy.provider_id, sell.provider_id))
        return tuple(pairs)

    def scan_tokens(self) -> tuple[TokenConfig, ...]:
        """Токены, участвующие в сканировании, в порядке ранга.

        Ограничивается ``level1.top_tokens`` (``01_PROJECT_REQUIREMENTS.md`` §7).
        Базовый токен в набор не входит: он является входом и выходом цикла.
        """
        candidates = [
            token
            for token in self.enabled_tokens
            if token.network_id == self.scanner.base_network
            and token.address != self.scanner.base_token_address
        ]
        candidates.sort(key=lambda token: (token.rank is None, token.rank or 0, token.symbol))
        return tuple(candidates[: self.scanner.level1.top_tokens])

    # --- версия конфигурации ----------------------------------------------

    @property
    def version(self) -> str:
        """Детерминированный отпечаток конфигурации.

        Позволяет отличить одну загруженную конфигурацию от другой
        (``17_CONFIGURATION.md`` §56). Секретов не содержит по построению:
        они не входят в модель.
        """
        return compute_fingerprint(self._fingerprint_payload())

    def _fingerprint_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        if not isinstance(payload, dict):  # pragma: no cover - защита от смены API pydantic
            raise TypeError("configuration dump must be a mapping")
        normalized = _stringify_floats(payload)
        if not isinstance(normalized, dict):  # pragma: no cover - структура сохраняется
            raise TypeError("configuration fingerprint payload must be a mapping")
        return normalized


def _stringify_floats(value: Any) -> Any:
    """Привести ``float`` к строке перед вычислением отпечатка.

    В конфигурации ``float`` используется только для операционных величин
    (таймауты, доли, частоты запросов) — финансовые значения хранятся как
    ``Decimal`` и сериализуются в строку. Отпечаток обязан отклонять
    ``float`` (см. :func:`compute_fingerprint`), поэтому операционные
    значения переводятся в детерминированное строковое представление.
    """
    if isinstance(value, dict):
        return {key: _stringify_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify_floats(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return repr(value)
    return value
