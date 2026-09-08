"""Level 2: несколько сумм, очередь, параллелизм и дедупликация workflow."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from monik.config import Configuration, parse_configuration
from monik.domain.enums.lifecycle import (
    AmountVerificationStatus,
    JobStatus,
    OpportunityStatus,
)
from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ResourceError
from monik.infrastructure.db import Database
from monik.infrastructure.providers.contract import QuoteRequest
from monik.infrastructure.providers.fake import FakeAdapter
from monik.services.level2 import Level2Worker
from monik.services.observability import FakeClock
from tests.component.level1.conftest import arbitrage_rule, level1_document
from tests.component.level2.conftest import build_level2
from tests.unit.config.conftest import VALID_ENV


def configured(**scanner_overrides: object) -> Configuration:
    return parse_configuration(level1_document(**scanner_overrides), environ=dict(VALID_ENV)).config


# --- несколько сумм -------------------------------------------------------


async def test_every_amount_is_verified(database: Database, clock: FakeClock) -> None:
    """Нельзя проверить только самую прибыльную сумму (§9)."""
    harness = await build_level2(configured(amounts=["100", "500"]), database, clock)
    result = await harness.scanner.confirm(harness.job)

    assert len(result.amount_results) == 2
    assert [item.input_amount.raw for item in result.amount_results] == [
        100_000_000,
        500_000_000,
    ]


async def test_amounts_share_the_route_but_not_the_result(
    database: Database, clock: FakeClock
) -> None:
    """Один маршрут, разные финансовые результаты (§7-8)."""
    harness = await build_level2(configured(amounts=["100", "500"]), database, clock)
    result = await harness.scanner.confirm(harness.job)

    routes = harness.opportunity.routes
    for amount in result.amount_results:
        assert amount.buy_quote is not None and amount.sell_quote is not None
        assert amount.buy_quote.route.fingerprint == routes.buy_route.fingerprint
        assert amount.sell_quote.route.fingerprint == routes.sell_route.fingerprint
    first, second = result.amount_results
    assert first.profit_result is not None and second.profit_result is not None
    assert first.profit_result.net_profit != second.profit_result.net_profit


async def test_partial_confirmation_is_not_hidden(database: Database, clock: FakeClock) -> None:
    """Смешанный результат отражается как PARTIAL (§46)."""

    def only_large_is_profitable(request: QuoteRequest) -> int:
        """Крупная сумма остаётся прибыльной, мелкая — нет."""
        if request.operation is OperationType.BUY:
            rate = Decimal("0.050")
        elif request.input_amount.as_decimal >= Decimal(20):
            rate = Decimal("20.30")
        else:
            rate = Decimal("20.05")
        return int((request.input_amount.as_decimal * rate).scaleb(request.output_token.decimals))

    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=only_large_is_profitable
        ),
    }
    harness = await build_level2(
        configured(amounts=["100", "500"]), database, clock, level2_adapter_set=adapters
    )
    result = await harness.scanner.confirm(harness.job)

    statuses = {item.status for item in result.amount_results}
    assert AmountVerificationStatus.VERIFIED_PROFITABLE in statuses
    assert AmountVerificationStatus.VERIFIED_UNPROFITABLE in statuses
    assert result.job_status is JobStatus.CONFIRMED
    opportunity = await harness.opportunities.get(harness.opportunity.opportunity_id)
    assert opportunity is not None and opportunity.status is OpportunityStatus.PARTIAL
    assert result.confirmed_count == 1
    assert result.unconfirmed_count == 1
    assert result.partial_count == 0


# --- очередь и параллелизм ------------------------------------------------


async def test_worker_confirms_submitted_job(database: Database, clock: FakeClock) -> None:
    """Job, переданный Level 1, обрабатывается немедленно (``02`` §46)."""
    harness = await build_level2(configured(), database, clock)
    worker = harness.worker

    await worker.submit(harness.opportunity, harness.job)
    results = await worker.drain()

    assert len(results) == 1
    assert results[0].job_status is JobStatus.CONFIRMED


async def test_identical_workflows_are_merged(database: Database, clock: FakeClock) -> None:
    """Одинаковые Level 2 workflow объединяются (``CLAUDE.md`` §19)."""
    gate = asyncio.Event()
    started = asyncio.Event()

    class _Blocking(FakeAdapter):
        async def get_quote(self, request: object) -> object:  # type: ignore[override]
            started.set()
            await gate.wait()
            return await super().get_quote(request)  # type: ignore[arg-type]

    adapters = {
        ProviderId.ONEINCH: _Blocking(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: _Blocking(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=adapters)
    worker = harness.worker

    await worker.submit(harness.opportunity, harness.job)
    await asyncio.wait_for(started.wait(), timeout=5)
    await worker.submit(harness.opportunity, harness.job)
    gate.set()
    results = await worker.drain()

    assert worker.merged_workflows == 1
    assert len(results) == 1


async def test_max_parallel_is_never_exceeded(database: Database, clock: FakeClock) -> None:
    """Число одновременных подтверждений ограничено (``CLAUDE.md`` §18)."""
    configuration = configured(level2={"max_parallel": 1, "queue_capacity": 10})
    harness = await build_level2(configuration, database, clock)
    assert harness.configuration.scanner.level2.max_parallel == 1

    worker = harness.worker
    await worker.submit(harness.opportunity, harness.job)
    await worker.drain()
    assert worker.active == 0


async def test_queue_capacity_creates_backpressure(database: Database, clock: FakeClock) -> None:
    """Очередь не растёт бесконечно (``03`` §69)."""
    harness = await build_level2(configured(), database, clock)
    worker = Level2Worker(
        harness.scanner,
        harness.configuration.scanner.level2.model_copy(update={"queue_capacity": 1}),
    )

    await worker.submit(harness.opportunity, harness.job)
    assert worker.available_capacity() == 0
    with pytest.raises(ResourceError):
        await worker.submit(harness.opportunity, harness.job)
    await worker.drain()
    assert worker.rejected_submissions == 1


async def test_worker_cancellation_stops_pending_jobs(database: Database, clock: FakeClock) -> None:
    """Shutdown отменяет принятые Job (``03`` §73)."""
    gate = asyncio.Event()
    started = asyncio.Event()

    class _Blocking(FakeAdapter):
        async def get_quote(self, request: object) -> object:  # type: ignore[override]
            started.set()
            await gate.wait()
            return await super().get_quote(request)  # type: ignore[arg-type]

    adapters = {
        ProviderId.ONEINCH: _Blocking(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: _Blocking(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=adapters)
    worker = harness.worker

    await worker.submit(harness.opportunity, harness.job)
    await asyncio.wait_for(started.wait(), timeout=5)
    await worker.cancel_all()
    gate.set()

    assert worker.results == []
    job = await harness.jobs.get(harness.job.k_id)
    assert job is not None and job.status is not JobStatus.CONFIRMED


async def test_route_unavailable_never_reaches_confirmed_through_worker(
    database: Database, clock: FakeClock
) -> None:
    """Невоспроизводимый маршрут не подтверждается и через очередь (§51)."""
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH,
            clock,
            output_rule=arbitrage_rule("0.050", "20.00"),
            fixed_route_outcome=RouteValidationOutcome.MISMATCH,
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=adapters)
    await harness.worker.submit(harness.opportunity, harness.job)
    results = await harness.worker.drain()

    assert results[0].job_status is JobStatus.REJECTED
    assert results[0].confirmed_count == 0
