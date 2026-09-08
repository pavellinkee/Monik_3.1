"""Composition root приложения.

Все зависимости собираются здесь **явно** (``25_PROJECT_STRUCTURE.md`` §8):
глобальных изменяемых singletons нет, каждая подсистема получает свои
зависимости через конструктор.

Порядок сборки соответствует ``CLAUDE.md`` §30: configuration → SQLite →
adapters → Resource Manager → подсистемы → Scheduler → Telegram → workers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlsplit

from monik.config.loader import LoadedConfiguration
from monik.config.root import Configuration
from monik.config.secrets import SecretValue
from monik.config.sections.fees import GasSource, PriceSource
from monik.config.sections.providers import ProviderConfig
from monik.domain.enums.notifications import DestinationKind
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ConfigurationError
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.db import Database
from monik.infrastructure.http import HttpClient, HttpxClient, UrlPolicy
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.infrastructure.providers.oneinch import OneInchAdapter
from monik.infrastructure.providers.oneinch import endpoints as oneinch_endpoints
from monik.infrastructure.providers.uniswap import UniswapAdapter
from monik.infrastructure.providers.uniswap import endpoints as uniswap_endpoints
from monik.infrastructure.providers.velora import VeloraAdapter
from monik.infrastructure.providers.velora import endpoints as velora_endpoints
from monik.infrastructure.providers.zero_x import ZeroXAdapter
from monik.infrastructure.providers.zero_x import endpoints as zero_x_endpoints
from monik.infrastructure.telegram.adapter import TelegramNotificationAdapter
from monik.infrastructure.telegram.polling import TelegramUpdateSource
from monik.repositories.sqlite import (
    SqliteCapabilityRepository,
    SqliteConfirmationRepository,
    SqliteFeeRepository,
    SqliteIdSequenceRepository,
    SqliteJobRepository,
    SqliteMetadataRepository,
    SqliteNotificationRepository,
    SqliteOpportunityRepository,
    SqliteScanRepository,
    SqliteSchedulerRepository,
    SqliteStateTransitionRepository,
)
from monik.services.calculator import ProfitCalculator
from monik.services.commands import (
    CommandRouter,
    CommandService,
    ComponentStatus,
    StatsSnapshot,
)
from monik.services.fees.policy import FeePolicy, QuoteInclusiveFeePolicy
from monik.services.fees.service import FeeService
from monik.services.gas.estimator import GasEstimator
from monik.services.gas.providers import (
    GasPriceProvider,
    RpcGasPriceProvider,
    StaticGasPriceProvider,
)
from monik.services.health.monitor import HealthMonitor
from monik.services.level1 import (
    CombinationFilter,
    Level1Scanner,
    PreliminaryEvaluator,
    ScopeBuilder,
)
from monik.services.level2 import (
    AmountVerifier,
    Level2Financials,
    Level2Scanner,
    Level2Worker,
    RouteVerifier,
)
from monik.services.notifications import MessageFormatter, NotificationDispatcher
from monik.services.observability import MetricsRegistry, TransitionRecorder
from monik.services.observability.clock import Clock
from monik.services.opportunity import OpportunityService
from monik.services.prices.conversion import ConversionService
from monik.services.prices.providers import (
    AggregatorQuotePriceProvider,
    HttpPriceProvider,
    TokenPriceProvider,
)
from monik.services.registries import (
    CapabilityRegistry,
    NetworkRegistry,
    ProviderRegistry,
    TokenRegistry,
)
from monik.services.resources import ResourceManager

__all__ = ["Container", "Repositories", "build_container"]

#: Фабрика HTTP-клиентов: каждая подсистема получает собственный клиент.
HttpClientFactory = Callable[[], HttpClient]

#: Базовые URL провайдеров по умолчанию: нужны для allowlist ещё до
#: создания адаптера.
_DEFAULT_BASE_URLS: dict[ProviderId, str] = {
    ProviderId.ONEINCH: oneinch_endpoints.DEFAULT_BASE_URL,
    ProviderId.ZERO_X: zero_x_endpoints.DEFAULT_BASE_URL,
    ProviderId.VELORA: velora_endpoints.DEFAULT_BASE_URL,
    ProviderId.UNISWAP: uniswap_endpoints.DEFAULT_BASE_URL,
}

#: Соответствие идентификатора провайдера его адаптеру.
_ADAPTERS: dict[ProviderId, type[OneInchAdapter | ZeroXAdapter | VeloraAdapter | UniswapAdapter]]
_ADAPTERS = {
    ProviderId.ONEINCH: OneInchAdapter,
    ProviderId.ZERO_X: ZeroXAdapter,
    ProviderId.VELORA: VeloraAdapter,
    ProviderId.UNISWAP: UniswapAdapter,
}


@dataclass
class Container:
    """Собранные подсистемы приложения."""

    configuration: Configuration
    clock: Clock
    database: Database
    metrics: MetricsRegistry
    health: HealthMonitor
    resources: ResourceManager
    http_clients: tuple[HttpClient, ...]
    adapters: dict[ProviderId, AggregatorAdapter]
    networks: NetworkRegistry
    tokens: TokenRegistry
    providers: ProviderRegistry
    capabilities: CapabilityRegistry
    fees: FeeService
    gas: GasEstimator
    conversion: ConversionService
    calculator: ProfitCalculator
    level1: Level1Scanner
    level2: Level2Scanner
    level2_worker: Level2Worker
    opportunities: OpportunityService
    notifications: NotificationDispatcher
    transitions: TransitionRecorder
    repositories: Repositories
    commands: CommandService | None = None
    telegram: TelegramNotificationAdapter | None = None
    formatter: MessageFormatter | None = None

    async def aclose(self) -> None:
        """Освободить внешние ресурсы."""
        for adapter in self.adapters.values():
            await adapter.aclose()
        if self.telegram is not None:
            await self.telegram.aclose()
        for client in self.http_clients:
            await client.aclose()


@dataclass
class Repositories:
    """Репозитории, используемые несколькими подсистемами."""

    jobs: SqliteJobRepository
    opportunities: SqliteOpportunityRepository
    notifications: SqliteNotificationRepository
    scans: SqliteScanRepository
    sequences: SqliteIdSequenceRepository
    scheduler: SqliteSchedulerRepository
    metadata: SqliteMetadataRepository
    transitions: SqliteStateTransitionRepository
    capabilities: SqliteCapabilityRepository
    fees: SqliteFeeRepository
    confirmations: SqliteConfirmationRepository
    _clients: list[HttpClient] = field(default_factory=list)


def build_container(
    loaded: LoadedConfiguration,
    *,
    database: Database,
    clock: Clock,
    metrics: MetricsRegistry | None = None,
    adapters: dict[ProviderId, AggregatorAdapter] | None = None,
) -> Container:
    """Собрать приложение из валидированной конфигурации.

    ``adapters`` позволяет composition root подставить готовый набор
    адаптеров (например детерминированные test implementations), не меняя
    остальную сборку.
    """
    config = loaded.config
    registry = metrics or MetricsRegistry()
    health = HealthMonitor(config.health, clock)
    url_policy = UrlPolicy(_allowed_hosts(loaded))
    clients: list[HttpClient] = []

    def http_client() -> HttpClient:
        client = HttpxClient(config.http, url_policy)
        clients.append(client)
        return client

    resources = ResourceManager(config.resources, clock)
    provider_adapters = (
        dict(adapters)
        if adapters is not None
        else _build_adapters(loaded, http_client=http_client, resources=resources, clock=clock)
    )

    networks = NetworkRegistry(config)
    tokens = TokenRegistry(config)
    providers = ProviderRegistry(config)
    repositories = _build_repositories(database)
    capabilities = CapabilityRegistry(repositories.capabilities, config.capabilities, clock)

    fees = FeeService(
        config.fees,
        clock,
        policies=_fee_policies(config),
        repository=repositories.fees,
    )
    gas = GasEstimator(
        clock,
        price_providers=_gas_providers(
            config, http_client=http_client, resources=resources, clock=clock, networks=networks
        ),
        native_tokens={
            str(network.network_id): networks.wrapped_native_token(network.network_id)
            for network in networks.enabled()
        },
    )
    conversion = ConversionService(
        clock,
        providers=_price_providers(
            config,
            adapters=provider_adapters,
            tokens=tokens,
            networks=networks,
            http_client=http_client,
            resources=resources,
            clock=clock,
        ),
    )
    calculator = ProfitCalculator(clock)
    transitions = TransitionRecorder(repositories.transitions, clock)

    level2_worker, level2 = _build_level2(
        config,
        adapters=provider_adapters,
        capabilities=capabilities,
        calculator=calculator,
        fees=fees,
        gas=gas,
        conversion=conversion,
        tokens=tokens,
        networks=networks,
        repositories=repositories,
        clock=clock,
        metrics=registry,
    )
    level1 = _build_level1(
        config,
        adapters=provider_adapters,
        capabilities=capabilities,
        calculator=calculator,
        fees=fees,
        gas=gas,
        conversion=conversion,
        tokens=tokens,
        networks=networks,
        providers=providers,
        repositories=repositories,
        dispatcher=level2_worker,
        clock=clock,
        metrics=registry,
    )

    formatter = MessageFormatter(config.notifications, tokens)
    opportunities = OpportunityService(
        publisher=repositories.confirmations,
        notifications=repositories.notifications,
        opportunities=repositories.opportunities,
        sequences=repositories.sequences,
        clock=clock,
        destinations=_destinations(loaded),
        renderer=formatter,
    )
    telegram = _build_telegram(loaded, http_client=http_client, resources=resources, clock=clock)
    notifications = NotificationDispatcher(
        config.notifications,
        store=repositories.notifications,
        transports=({DestinationKind.TELEGRAM.value: telegram} if telegram else {}),
        clock=clock,
        metrics=registry,
    )
    commands = _build_commands(
        loaded,
        repositories=repositories,
        telegram=telegram,
        http_client=http_client,
        resources=resources,
        clock=clock,
        health=health,
    )

    return Container(
        configuration=config,
        clock=clock,
        database=database,
        metrics=registry,
        health=health,
        resources=resources,
        http_clients=tuple(clients),
        adapters=provider_adapters,
        networks=networks,
        tokens=tokens,
        providers=providers,
        capabilities=capabilities,
        fees=fees,
        gas=gas,
        conversion=conversion,
        calculator=calculator,
        level1=level1,
        level2=level2,
        level2_worker=level2_worker,
        opportunities=opportunities,
        notifications=notifications,
        transitions=transitions,
        repositories=repositories,
        commands=commands,
        telegram=telegram,
        formatter=formatter,
    )


# --- сборка отдельных частей ---------------------------------------------


def _allowed_hosts(loaded: LoadedConfiguration) -> tuple[str, ...]:
    """Хосты, к которым приложению разрешено обращаться.

    Allowlist строится из фактически настроенных endpoints: провайдеров,
    RPC, price API и Telegram (``32_SECURITY.md``). Всё остальное
    блокируется политикой URL ещё до отправки запроса.
    """
    config = loaded.config
    urls: list[str] = list(config.http.extra_allowed_hosts)
    for provider in config.providers:
        if not provider.enabled:
            continue
        default = _DEFAULT_BASE_URLS.get(provider.provider_id)
        base_url = provider.base_url or default
        if base_url:
            urls.append(base_url)
    for network in config.networks:
        if network.enabled and network.rpc_url:
            urls.append(network.rpc_url)
    if config.prices.http_endpoint:
        urls.append(config.prices.http_endpoint)
    if config.notifications.telegram.enabled:
        urls.append(config.notifications.telegram.api_base_url)
    return tuple(sorted({_host_of(url) for url in urls if url}))


def _host_of(value: str) -> str:
    """Имя хоста из URL или уже готового имени."""
    if "://" not in value:
        return value.strip().lower()
    return urlsplit(value).hostname or ""


def _build_repositories(database: Database) -> Repositories:
    """Репозитории поверх одного соединения с базой."""
    return Repositories(
        jobs=SqliteJobRepository(database),
        opportunities=SqliteOpportunityRepository(database),
        notifications=SqliteNotificationRepository(database),
        scans=SqliteScanRepository(database),
        sequences=SqliteIdSequenceRepository(database),
        scheduler=SqliteSchedulerRepository(database),
        metadata=SqliteMetadataRepository(database),
        transitions=SqliteStateTransitionRepository(database),
        capabilities=SqliteCapabilityRepository(database),
        fees=SqliteFeeRepository(database),
        confirmations=SqliteConfirmationRepository(database),
    )


def _build_adapters(
    loaded: LoadedConfiguration,
    *,
    http_client: HttpClientFactory,
    resources: ResourceManager,
    clock: Clock,
) -> dict[ProviderId, AggregatorAdapter]:
    """Адаптеры включённых провайдеров.

    Отключённый провайдер адаптер не получает: запросы к нему не
    выполняются (``02_LEVEL1_SCANNER.md`` §71).
    """
    adapters: dict[ProviderId, AggregatorAdapter] = {}
    for provider in loaded.config.providers:
        if not provider.enabled:
            continue
        factory = _ADAPTERS.get(provider.provider_id)
        if factory is None:  # pragma: no cover - защита от нового провайдера
            continue
        adapters[provider.provider_id] = factory(
            provider,
            http=http_client(),
            resources=resources,
            clock=clock,
            api_key=_provider_secret(loaded, provider),
        )
    return adapters


def _provider_secret(loaded: LoadedConfiguration, provider: ProviderConfig) -> SecretValue | None:
    """Разрешённый API-ключ провайдера, если он задан."""
    if provider.api_key is None:
        return None
    return loaded.secrets.get(provider.api_key)


def _fee_policies(config: Configuration) -> dict[ProviderId, FeePolicy]:
    """Политики комиссий включённых провайдеров.

    Агрегаторы возвращают итоговую сумму маршрута, поэтому комиссия уже
    учтена в котировке (``01_PROJECT_REQUIREMENTS.md`` §29). Провайдер без
    политики получает ``UNKNOWN``, а не ноль.
    """
    return {
        provider.provider_id: QuoteInclusiveFeePolicy(
            provider.provider_id, source=f"policy:{provider.provider_id.value}"
        )
        for provider in config.providers
        if provider.enabled
    }


def _gas_providers(
    config: Configuration,
    *,
    http_client: HttpClientFactory,
    resources: ResourceManager,
    clock: Clock,
    networks: NetworkRegistry,
) -> tuple[GasPriceProvider, ...]:
    """Источники цены газа согласно конфигурации (решение D-4)."""
    providers: list[GasPriceProvider] = []
    if GasSource.STATIC in config.gas.sources and config.gas.static_wei_per_gas:
        providers.append(StaticGasPriceProvider(clock, prices=dict(config.gas.static_wei_per_gas)))
    if GasSource.RPC in config.gas.sources:
        rpc_urls = {
            str(network.network_id): url
            for network in networks.enabled()
            if (url := networks.rpc_url(network.network_id)) is not None
        }
        if rpc_urls:
            providers.append(
                RpcGasPriceProvider(
                    http=http_client(),
                    resources=resources,
                    clock=clock,
                    rpc_urls=rpc_urls,
                    freshness_seconds=config.gas.freshness_seconds,
                    timeout_seconds=config.gas.request_timeout_seconds,
                )
            )
    if not providers:
        raise ConfigurationError(
            "no usable gas price source is configured: set network rpc_url for the rpc "
            "source or configure gas.static_wei_per_gas; unknown gas is never zero"
        )
    return tuple(providers)


def _price_providers(
    config: Configuration,
    *,
    adapters: dict[ProviderId, AggregatorAdapter],
    tokens: TokenRegistry,
    networks: NetworkRegistry,
    http_client: HttpClientFactory,
    resources: ResourceManager,
    clock: Clock,
) -> tuple[TokenPriceProvider, ...]:
    """Источники курса native token (решение D-4)."""
    providers: list[TokenPriceProvider] = []
    if PriceSource.AGGREGATOR_QUOTE in config.prices.sources and adapters:
        adapter = next(iter(adapters.values()))
        providers.append(
            AggregatorQuotePriceProvider(
                adapter,
                clock,
                # Пробная сумма — один native token: курс берётся из
                # исполнимой котировки, а не из абстрактной цены.
                probe_amount_raw=_native_probe_amount(config, tokens=tokens, networks=networks),
                ttl_seconds=config.prices.freshness_seconds,
            )
        )
    if PriceSource.HTTP in config.prices.sources and config.prices.http_endpoint:
        providers.append(
            HttpPriceProvider(
                http=http_client(),
                resources=resources,
                clock=clock,
                endpoint=config.prices.http_endpoint,
                ttl_seconds=config.prices.freshness_seconds,
                timeout_seconds=config.prices.request_timeout_seconds,
            )
        )
    if not providers:
        raise ConfigurationError(
            "no usable price source is configured; gas cost could not be converted"
        )
    return tuple(providers)


def _native_probe_amount(
    config: Configuration, *, tokens: TokenRegistry, networks: NetworkRegistry
) -> int:
    """Один native token сети в base units."""
    native_key = networks.wrapped_native_token(config.scanner.base_network)
    native = tokens.get(native_key)
    decimals: int = native.decimals if native is not None else 18
    return int(10**decimals)


def _build_level2(
    config: Configuration,
    *,
    adapters: dict[ProviderId, AggregatorAdapter],
    capabilities: CapabilityRegistry,
    calculator: ProfitCalculator,
    fees: FeeService,
    gas: GasEstimator,
    conversion: ConversionService,
    tokens: TokenRegistry,
    networks: NetworkRegistry,
    repositories: Repositories,
    clock: Clock,
    metrics: MetricsRegistry,
) -> tuple[Level2Worker, Level2Scanner]:
    """Level 2 вместе с его очередью."""
    verifier = AmountVerifier(
        RouteVerifier(
            adapters,
            capabilities,
            clock,
            quote_max_age=timedelta(seconds=config.scanner.level2.quote_max_age_seconds),
        ),
        Level2Financials(
            calculator,
            fees=fees,
            gas=gas,
            rates=conversion,
            tokens=tokens,
            networks=networks,
            profitability=config.profitability,
        ),
        tokens,
    )
    scanner = Level2Scanner(
        config.scanner.level2,
        verifier=verifier,
        jobs=repositories.jobs,
        opportunities=repositories.opportunities,
        clock=clock,
        metrics=metrics,
    )
    return Level2Worker(scanner, config.scanner.level2), scanner


def _build_level1(
    config: Configuration,
    *,
    adapters: dict[ProviderId, AggregatorAdapter],
    capabilities: CapabilityRegistry,
    calculator: ProfitCalculator,
    fees: FeeService,
    gas: GasEstimator,
    conversion: ConversionService,
    tokens: TokenRegistry,
    networks: NetworkRegistry,
    providers: ProviderRegistry,
    repositories: Repositories,
    dispatcher: Level2Worker,
    clock: Clock,
    metrics: MetricsRegistry,
) -> Level1Scanner:
    """Level 1 со всеми зависимостями."""
    return Level1Scanner(
        config,
        adapters=adapters,
        scope_builder=ScopeBuilder(config, networks=networks, tokens=tokens, providers=providers),
        combinations=CombinationFilter(capabilities, config.scanner.level1),
        evaluator=PreliminaryEvaluator(
            calculator,
            fees=fees,
            gas=gas,
            rates=conversion,
            tokens=tokens,
            networks=networks,
            profitability=config.profitability,
        ),
        opportunities=repositories.opportunities,
        scans=repositories.scans,
        sequences=repositories.sequences,
        dispatcher=dispatcher,
        clock=clock,
        metrics=metrics,
    )


def _destinations(loaded: LoadedConfiguration) -> tuple[NotificationDestination, ...]:
    """Настроенные назначения доставки (``15_NOTIFICATION_SYSTEM.md`` §53)."""
    telegram = loaded.config.notifications.telegram
    if not (loaded.config.notifications.enabled and telegram.enabled and telegram.chat_id):
        return ()
    return (
        NotificationDestination(
            destination_id=telegram.chat_id.env,
            kind=DestinationKind.TELEGRAM,
            mode=loaded.config.notifications.mode,
        ),
    )


def _build_telegram(
    loaded: LoadedConfiguration,
    *,
    http_client: HttpClientFactory,
    resources: ResourceManager,
    clock: Clock,
) -> TelegramNotificationAdapter | None:
    """Адаптер доставки, если Telegram настроен."""
    telegram = loaded.config.notifications.telegram
    if not telegram.enabled or telegram.bot_token is None or telegram.chat_id is None:
        return None
    return TelegramNotificationAdapter(
        telegram,
        http=http_client(),
        resources=resources,
        clock=clock,
        bot_token=loaded.secrets.get(telegram.bot_token),
        chat_id=loaded.secrets.get(telegram.chat_id),
    )


def _build_commands(
    loaded: LoadedConfiguration,
    *,
    repositories: Repositories,
    telegram: TelegramNotificationAdapter | None,
    http_client: HttpClientFactory,
    resources: ResourceManager,
    clock: Clock,
    health: HealthMonitor,
) -> CommandService | None:
    """Входящий канал команд, если он включён конфигурацией."""
    config = loaded.config.notifications.telegram
    if telegram is None or not config.commands_enabled or config.bot_token is None:
        return None
    destinations = _destinations(loaded)
    if not destinations:
        return None
    router = CommandRouter(
        jobs=repositories.jobs,
        notifications=repositories.notifications,
        status=_HealthStatusSource(health),
        stats=_MetricsStatsSource(),
    )
    return CommandService(
        router=router,
        updates=TelegramUpdateSource(
            config,
            http=http_client(),
            resources=resources,
            clock=clock,
            bot_token=loaded.secrets.get(config.bot_token),
        ),
        transport=telegram,
        destination=destinations[0],
        offsets=repositories.metadata,
        clock=clock,
    )


class _HealthStatusSource:
    """Снимок состояния подсистем для команды ``/status``."""

    def __init__(self, health: HealthMonitor) -> None:
        self._health = health

    def components(self) -> tuple[ComponentStatus, ...]:
        """Состояние подсистем из Health Monitor."""
        snapshot = self._health.application_health()
        components = tuple(
            ComponentStatus(name=item.component, state=item.status.value, detail=item.reason)
            for item in snapshot.components
        )
        providers = tuple(
            ComponentStatus(name=f"provider:{item.provider_id.value}", state=item.status.value)
            for item in snapshot.providers
        )
        return (
            ComponentStatus(name="application", state=snapshot.status.value),
            *components,
            *providers,
        )


class _MetricsStatsSource:
    """Статистика для команды ``/stats``.

    Значения накапливает Opportunity Service и подсистемы; здесь они только
    отдаются командой. Пересчёта не выполняется.
    """

    def __init__(self) -> None:
        self._snapshot = StatsSnapshot()

    def update(self, snapshot: StatsSnapshot) -> None:
        """Обновить отдаваемую статистику."""
        self._snapshot = snapshot

    def snapshot(self) -> StatsSnapshot:
        """Текущая статистика."""
        return self._snapshot
