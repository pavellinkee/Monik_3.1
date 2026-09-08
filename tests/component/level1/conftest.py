"""Тестовое окружение Level 1.

Все внешние зависимости заменены детерминированными **test
implementations** (``CLAUDE.md`` §10): адаптеры, Fee System, gas, курсы и
приёмник Level 2. База данных настоящая — атомарность создания Opportunity
проверяется на реальной схеме.
"""

from __future__ import annotations

import copy
import pathlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from monik.config import Configuration, parse_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.conversion import ConversionRate
from monik.domain.models.fee import Fee, FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.job import Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.domain.models.token import Token
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.providers.contract import QuoteRequest
from monik.infrastructure.providers.fake import FakeAdapter
from monik.repositories.sqlite import (
    SqliteCapabilityRepository,
    SqliteIdSequenceRepository,
    SqliteOpportunityRepository,
    SqliteScanRepository,
)
from monik.services.calculator import ProfitCalculator
from monik.services.fees.context import FeeContext
from monik.services.level1 import (
    CombinationFilter,
    Level1Scanner,
    PreliminaryEvaluator,
    ScopeBuilder,
)
from monik.services.observability import FakeClock, MetricsRegistry
from monik.services.registries import (
    CapabilityRegistry,
    NetworkRegistry,
    ProviderRegistry,
    TokenRegistry,
)
from tests import factories as f
from tests.unit.config.conftest import VALID_ENV, base_document

WMATIC_ADDRESS = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"


def level1_document(**scanner_overrides: Any) -> dict[str, Any]:
    """Конфигурация цикла Level 1.

    WMATIC присутствует как native token сети, но выключен: он нужен для
    конверсии газа и не должен сканироваться как промежуточный токен.
    """
    document = copy.deepcopy(base_document())
    document["tokens"].append(
        {
            "network_id": "polygon",
            "address": WMATIC_ADDRESS,
            "symbol": "WMATIC",
            "decimals": 18,
            "rank": 9,
            "enabled": False,
        }
    )
    document["scanner"]["amounts"] = ["100"]
    document["scanner"].update(scanner_overrides)
    return document


@pytest.fixture
def configuration() -> Configuration:
    return parse_configuration(level1_document(), environ=dict(VALID_ENV)).config


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "level1.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


# --- test implementations --------------------------------------------------


def arbitrage_rule(buy_rate: str, sell_rate: str) -> Callable[[QuoteRequest], int]:
    """Правило выдачи output: разный курс для BUY и SELL."""

    def rule(request: QuoteRequest) -> int:
        rate = Decimal(buy_rate) if request.operation is OperationType.BUY else Decimal(sell_rate)
        human = request.input_amount.as_decimal * rate
        return int(human.scaleb(request.output_token.decimals))

    return rule


class StaticFeeSource:
    """Комиссии, подтверждённо известные для обеих ног.

    Реализует и ``FeeSource``, и ``FeeSnapshotSource``: Level 2 сохраняет
    версионированный снимок комиссий.
    """

    def __init__(self, *, amount: str = "0.10", fees: tuple[Fee, ...] | None = None) -> None:
        self._amount = amount
        self._fees = fees
        self.calls: list[FeeContext] = []
        self.snapshot_calls: list[FeeContext] = []

    async def snapshot_for(self, context: FeeContext) -> FeeSnapshot:
        self.snapshot_calls.append(context)
        return FeeSnapshot(
            snapshot_id=context.cache_key()[:64],
            provider_id=context.provider_id,
            network_id=context.network_id,
            operation=context.operation,
            fees=await self.fees_for(context),
            version=1,
            created_at=f.NOW,
        )

    async def fees_for(self, context: FeeContext) -> tuple[Fee, ...]:
        self.calls.append(context)
        if self._fees is not None:
            return self._fees
        return (
            Fee(
                fee_type=FeeType.AGGREGATOR,
                status=FeeStatus.KNOWN,
                amount=Decimal(self._amount),
                currency=f.USDT.key,
                inclusion=CostInclusion.NOT_INCLUDED,
                source="test",
                observed_at=f.NOW,
            ),
        )


class StaticGasSource:
    """Оценка газа без обращения к RPC."""

    def __init__(self, gas: Gas | None = None) -> None:
        self._gas = gas
        self.calls: list[int | None] = []

    async def estimate(
        self,
        network_id: NetworkId,
        *,
        gas_units: int | None,
        source: str = "gas_estimator",
    ) -> Gas:
        self.calls.append(gas_units)
        if self._gas is not None:
            return self._gas
        if gas_units is None:
            return Gas(
                network_id=network_id,
                status=FeeStatus.UNKNOWN,
                observed_at=f.NOW,
                source=source,
            )
        return f.known_gas(cost_native="0.03")


class StaticRateSource:
    """Курс native token в валюту расчёта."""

    def __init__(self, rate: str | None = "0.50") -> None:
        self._rate = rate

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        if self._rate is None:
            return None
        return ConversionRate(
            from_token=from_token.key,
            to_token=to_token.key,
            rate=Decimal(self._rate),
            source="test",
            observed_at=f.NOW,
        )


@dataclass
class RecordingDispatcher:
    """Приёмник Level 2 Job с ограниченной ёмкостью."""

    capacity: int = 100
    submitted: list[tuple[Opportunity, Level2Job]] = field(default_factory=list)

    def available_capacity(self) -> int:
        return max(self.capacity - len(self.submitted), 0)

    async def submit(self, opportunity: Opportunity, job: Level2Job) -> None:
        self.submitted.append((opportunity, job))


@dataclass
class Level1Harness:
    """Собранный Level 1 со всеми test implementations."""

    scanner: Level1Scanner
    configuration: Configuration
    clock: FakeClock
    adapters: dict[ProviderId, FakeAdapter]
    dispatcher: RecordingDispatcher
    fees: StaticFeeSource
    gas: StaticGasSource
    rates: StaticRateSource
    capabilities: CapabilityRegistry
    opportunities: SqliteOpportunityRepository
    scans: SqliteScanRepository
    tokens: TokenRegistry


def build_harness(
    configuration: Configuration,
    database: Database,
    clock: FakeClock,
    *,
    adapters: dict[ProviderId, FakeAdapter] | None = None,
    fees: StaticFeeSource | None = None,
    gas: StaticGasSource | None = None,
    rates: StaticRateSource | None = None,
    dispatcher: RecordingDispatcher | None = None,
    metrics: MetricsRegistry | None = None,
) -> Level1Harness:
    """Собрать Level 1 со всеми зависимостями."""
    networks = NetworkRegistry(configuration)
    tokens = TokenRegistry(configuration)
    providers = ProviderRegistry(configuration)
    capabilities = CapabilityRegistry(
        SqliteCapabilityRepository(database), configuration.capabilities, clock
    )
    resolved_adapters: dict[ProviderId, FakeAdapter] = adapters or {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    fee_source = fees or StaticFeeSource()
    gas_source = gas or StaticGasSource()
    rate_source = rates or StaticRateSource()
    level2 = dispatcher or RecordingDispatcher()
    scope_builder = ScopeBuilder(
        configuration, networks=networks, tokens=tokens, providers=providers
    )
    evaluator = PreliminaryEvaluator(
        ProfitCalculator(clock),
        fees=fee_source,
        gas=gas_source,
        rates=rate_source,
        tokens=tokens,
        networks=networks,
        profitability=configuration.profitability,
    )
    opportunity_repository = SqliteOpportunityRepository(database)
    scan_repository = SqliteScanRepository(database)
    scanner = Level1Scanner(
        configuration,
        adapters=dict(resolved_adapters),
        scope_builder=scope_builder,
        combinations=CombinationFilter(capabilities, configuration.scanner.level1),
        evaluator=evaluator,
        opportunities=opportunity_repository,
        scans=scan_repository,
        sequences=SqliteIdSequenceRepository(database),
        dispatcher=level2,
        clock=clock,
        metrics=metrics,
    )
    return Level1Harness(
        scanner=scanner,
        configuration=configuration,
        clock=clock,
        adapters=resolved_adapters,
        dispatcher=level2,
        fees=fee_source,
        gas=gas_source,
        rates=rate_source,
        capabilities=capabilities,
        opportunities=opportunity_repository,
        scans=scan_repository,
        tokens=tokens,
    )


@pytest.fixture
def harness(configuration: Configuration, database: Database, clock: FakeClock) -> Level1Harness:
    return build_harness(configuration, database, clock)


async def mark_unsupported(
    registry: CapabilityRegistry,
    provider_id: ProviderId,
    operation: CapabilityOperation,
    token: Token,
) -> None:
    """Явно объявить комбинацию неподдерживаемой."""
    await registry.record_discovery(
        registry.key(provider_id, NetworkId("polygon"), operation, token.key),
        CapabilityStatus.UNSUPPORTED,
        source="test",
    )
