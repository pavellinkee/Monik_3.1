"""Тестовое окружение Level 2.

Opportunity создаётся настоящим Level 1 на тех же адаптерах: только так
отпечатки маршрутов Opportunity и проверочных котировок совпадают, а
проверка «тот же маршрут» имеет смысл.
"""

from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta

import pytest

from monik.config import Configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.enums.providers import ProviderId
from monik.domain.models.job import Level2Job
from monik.domain.models.opportunity import Opportunity
from monik.infrastructure.db import Database, MigrationRunner
from monik.infrastructure.providers.fake import FakeAdapter
from monik.repositories.sqlite import (
    SqliteCapabilityRepository,
    SqliteJobRepository,
    SqliteOpportunityRepository,
)
from monik.services.calculator import ProfitCalculator
from monik.services.level2 import (
    AmountVerifier,
    Level2Financials,
    Level2Scanner,
    Level2Worker,
    RouteVerifier,
)
from monik.services.observability import FakeClock
from monik.services.registries import CapabilityRegistry, NetworkRegistry, TokenRegistry
from tests import factories as f
from tests.component.level1.conftest import (
    StaticFeeSource,
    StaticGasSource,
    StaticRateSource,
    arbitrage_rule,
    build_harness,
)


@pytest.fixture
async def database(tmp_path: pathlib.Path) -> AsyncIterator[Database]:
    instance = Database(DatabaseConfig(path=str(tmp_path / "level2.db"), busy_timeout_seconds=1.0))
    await instance.connect()
    await MigrationRunner(instance).upgrade()
    try:
        yield instance
    finally:
        await instance.close()


@dataclass
class Level2Harness:
    """Собранный Level 2 вместе с проверяемой Opportunity."""

    scanner: Level2Scanner
    worker: Level2Worker
    opportunity: Opportunity
    job: Level2Job
    adapters: dict[ProviderId, FakeAdapter]
    fees: StaticFeeSource
    gas: StaticGasSource
    rates: StaticRateSource
    jobs: SqliteJobRepository
    opportunities: SqliteOpportunityRepository
    capabilities: CapabilityRegistry
    clock: FakeClock
    configuration: Configuration


def level1_adapters(clock: FakeClock) -> dict[ProviderId, FakeAdapter]:
    """Адаптеры, дающие прибыльный цикл USDT -> AAVE -> USDT."""
    return {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }


async def build_level2(
    configuration: Configuration,
    database: Database,
    clock: FakeClock,
    *,
    level1_adapter_set: dict[ProviderId, FakeAdapter] | None = None,
    level2_adapter_set: dict[ProviderId, FakeAdapter] | None = None,
    fees: StaticFeeSource | None = None,
    gas: StaticGasSource | None = None,
    rates: StaticRateSource | None = None,
) -> Level2Harness:
    """Создать Opportunity через Level 1 и собрать над ней Level 2."""
    level1 = build_harness(
        configuration, database, clock, adapters=level1_adapter_set or level1_adapters(clock)
    )
    scan = await level1.scanner.scan()
    assert scan.opportunities, "фикстуре нужна созданная Level 1 возможность"
    opportunity, job = level1.dispatcher.submitted[0]

    adapters = level2_adapter_set or level1.adapters
    tokens = TokenRegistry(configuration)
    networks = NetworkRegistry(configuration)
    capabilities = CapabilityRegistry(
        SqliteCapabilityRepository(database), configuration.capabilities, clock
    )
    fee_source = fees or StaticFeeSource()
    gas_source = gas or StaticGasSource()
    rate_source = rates or StaticRateSource()
    verifier = AmountVerifier(
        RouteVerifier(
            dict(adapters),
            capabilities,
            clock,
            quote_max_age=timedelta(seconds=configuration.scanner.level2.quote_max_age_seconds),
        ),
        Level2Financials(
            ProfitCalculator(clock),
            fees=fee_source,
            gas=gas_source,
            rates=rate_source,
            tokens=tokens,
            networks=networks,
            profitability=configuration.profitability,
        ),
        tokens,
    )
    jobs = SqliteJobRepository(database)
    opportunities = SqliteOpportunityRepository(database)
    scanner = Level2Scanner(
        configuration.scanner.level2,
        verifier=verifier,
        jobs=jobs,
        opportunities=opportunities,
        clock=clock,
    )
    return Level2Harness(
        scanner=scanner,
        worker=Level2Worker(scanner, configuration.scanner.level2),
        opportunity=opportunity,
        job=job,
        adapters=dict(adapters),
        fees=fee_source,
        gas=gas_source,
        rates=rate_source,
        jobs=jobs,
        opportunities=opportunities,
        capabilities=capabilities,
        clock=clock,
        configuration=configuration,
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)
