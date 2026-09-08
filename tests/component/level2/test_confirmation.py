"""Level 2: подтверждение на зафиксированном маршруте.

Покрывает обязательный список ``11_LEVEL_2_SCANNER.md`` §75 и
``03_LEVEL2_SCANNER.md`` §85.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest

from monik.config import Configuration, parse_configuration
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.lifecycle import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
    OpportunityStatus,
)
from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DomainValidationError, RateLimitError
from monik.domain.errors import TimeoutError as MonikTimeoutError
from monik.infrastructure.db import Database
from monik.infrastructure.providers.fake import FakeAdapter
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.level1.conftest import (
    StaticFeeSource,
    StaticGasSource,
    StaticRateSource,
    arbitrage_rule,
    level1_document,
)
from tests.component.level2.conftest import Level2Harness, build_level2
from tests.unit.config.conftest import VALID_ENV


def configured(**scanner_overrides: object) -> Configuration:
    return parse_configuration(level1_document(**scanner_overrides), environ=dict(VALID_ENV)).config


@pytest.fixture
async def harness(database: Database, clock: FakeClock) -> Level2Harness:
    return await build_level2(configured(), database, clock)


# --- подтверждение --------------------------------------------------------


async def test_same_route_verification_confirms(harness: Level2Harness) -> None:
    """Возможность подтверждается на том же маршруте (§45, §77)."""
    result = await harness.scanner.confirm(harness.job)

    assert result.job_status is JobStatus.CONFIRMED
    assert result.confirmed_count == 1
    assert result.amount_results[0].status is AmountVerificationStatus.VERIFIED_PROFITABLE
    assert result.failure_reason is None


async def test_confirmation_updates_job_and_opportunity(harness: Level2Harness) -> None:
    """Итог фиксируется в Job и Opportunity (§47)."""
    await harness.scanner.confirm(harness.job)

    job = await harness.jobs.get(harness.job.k_id)
    opportunity = await harness.opportunities.get(harness.opportunity.opportunity_id)
    assert job is not None and job.status is JobStatus.CONFIRMED
    assert opportunity is not None and opportunity.status is OpportunityStatus.CONFIRMED


async def test_level2_never_changes_the_route(harness: Level2Harness) -> None:
    """Level 2 запрашивает строго зафиксированный маршрут (§5, §61, §76.1-2)."""
    result = await harness.scanner.confirm(harness.job)

    routes = harness.opportunity.routes
    requests = [
        call
        for adapter in harness.adapters.values()
        for call in adapter.quote_calls
        if call.fixed_route is not None
    ]
    assert requests, "Level 2 обязан передавать зафиксированный маршрут"
    fingerprints = {str(call.fixed_route.fingerprint) for call in requests if call.fixed_route}
    assert fingerprints == {
        str(routes.buy_route.fingerprint),
        str(routes.sell_route.fingerprint),
    }
    amount = result.amount_results[0]
    assert amount.buy_quote is not None and amount.sell_quote is not None
    assert amount.buy_quote.route.fingerprint == routes.buy_route.fingerprint
    assert amount.sell_quote.route.fingerprint == routes.sell_route.fingerprint
    assert amount.buy_quote.provider_id is harness.opportunity.buy_provider_id
    assert amount.sell_quote.provider_id is harness.opportunity.sell_provider_id


async def test_sell_uses_the_current_buy_output(database: Database, clock: FakeClock) -> None:
    """SELL проверяется на текущем BUY output, а не на значении Level 1 (§16-17)."""
    level2_adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.048", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    amount = result.amount_results[0]
    assert amount.current_buy_output is not None
    # Level 1 нашёл 5.0 AAVE, Level 2 получил 4.8 — SELL считается от 4.8.
    assert amount.current_buy_output.as_decimal == Decimal("4.8")
    assert harness.opportunity.amounts[0].preliminary_buy_output.as_decimal == Decimal(5)
    sell_calls = [
        call
        for adapter in harness.adapters.values()
        for call in adapter.quote_calls
        if call.operation is OperationType.SELL
    ]
    assert sell_calls[-1].input_amount == amount.current_buy_output


async def test_level1_quote_is_not_reused(harness: Level2Harness) -> None:
    """Level 1 quote не является свежим подтверждением (§12-13)."""
    before = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    await harness.scanner.confirm(harness.job)
    after = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    assert after > before


# --- маршрут не воспроизводится ------------------------------------------


async def test_route_mismatch_is_not_unprofitable(database: Database, clock: FakeClock) -> None:
    """Несоответствие маршрута — отдельная причина, не убыточность (§51)."""
    level2_adapters = {
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
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    amount = result.amount_results[0]
    assert amount.status is AmountVerificationStatus.ROUTE_UNAVAILABLE
    assert amount.status is not AmountVerificationStatus.VERIFIED_UNPROFITABLE
    assert result.job_status is JobStatus.REJECTED
    opportunity = await harness.opportunities.get(harness.opportunity.opportunity_id)
    assert opportunity is not None
    assert opportunity.status is OpportunityStatus.ROUTE_UNAVAILABLE


async def test_fixed_route_unsupported_does_not_pick_an_alternative(
    database: Database, clock: FakeClock
) -> None:
    """Адаптер без поддержки fixed route не даёт молча заменить маршрут (§22, §24)."""
    level2_adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH,
            clock,
            output_rule=arbitrage_rule("0.050", "20.00"),
            fixed_route_outcome=RouteValidationOutcome.UNSUPPORTED,
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is AmountVerificationStatus.ROUTE_UNAVAILABLE
    assert result.job_status is JobStatus.REJECTED


async def test_unsupported_capability_blocks_verification(
    database: Database, clock: FakeClock
) -> None:
    """Явно неподдерживаемый fixed route блокирует запрос (§22)."""
    harness = await build_level2(configured(), database, clock)
    registry = harness.capabilities
    await registry.record_discovery(
        registry.key(ProviderId.ONEINCH, f.POLYGON, CapabilityOperation.FIXED_ROUTE),
        CapabilityStatus.UNSUPPORTED,
        source="test",
    )
    calls_before = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())

    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is AmountVerificationStatus.ROUTE_UNAVAILABLE
    calls_after = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    assert calls_after == calls_before, "неподдерживаемый маршрут не запрашивается"


# --- расходы и порог ------------------------------------------------------


async def test_unknown_gas_never_yields_confirmed(database: Database, clock: FakeClock) -> None:
    """Неизвестный критический расход не даёт CONFIRMED (§35, §76.10)."""
    harness = await build_level2(
        configured(), database, clock, gas=StaticGasSource(f.unknown_gas())
    )
    result = await harness.scanner.confirm(harness.job)

    amount = result.amount_results[0]
    assert amount.status is AmountVerificationStatus.UNKNOWN
    assert amount.confirmation_status is AmountConfirmationStatus.PARTIAL
    assert result.job_status is not JobStatus.CONFIRMED
    assert result.confirmed_count == 0


async def test_unknown_fee_never_yields_confirmed(database: Database, clock: FakeClock) -> None:
    """UNKNOWN fee не считается нулём (§35)."""
    harness = await build_level2(
        configured(), database, clock, fees=StaticFeeSource(fees=(f.unknown_fee(),))
    )
    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is AmountVerificationStatus.UNKNOWN
    assert result.confirmed_count == 0


async def test_missing_conversion_never_yields_confirmed(
    database: Database, clock: FakeClock
) -> None:
    """Без курса стоимость газа неизвестна (§36)."""
    harness = await build_level2(configured(), database, clock, rates=StaticRateSource(None))
    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is AmountVerificationStatus.UNKNOWN


async def test_result_below_threshold_is_unprofitable(database: Database, clock: FakeClock) -> None:
    """Ниже порога — VERIFIED_UNPROFITABLE (§50)."""
    level2_adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.05")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    amount = result.amount_results[0]
    assert amount.status is AmountVerificationStatus.VERIFIED_UNPROFITABLE
    assert amount.confirmation_status is AmountConfirmationStatus.UNCONFIRMED
    assert result.job_status is JobStatus.REJECTED
    opportunity = await harness.opportunities.get(harness.opportunity.opportunity_id)
    assert opportunity is not None and opportunity.status is OpportunityStatus.UNPROFITABLE


async def test_fee_snapshots_are_stored_for_audit(harness: Level2Harness) -> None:
    """Снимок комиссий сохраняется для аудита подтверждения (§65-67)."""
    result = await harness.scanner.confirm(harness.job)
    amount = result.amount_results[0]

    assert len(amount.fee_snapshots) == 2
    assert {snapshot.operation for snapshot in amount.fee_snapshots} == {
        OperationType.BUY,
        OperationType.SELL,
    }
    assert amount.gas is not None
    assert amount.profit_result is not None
    assert amount.profit_result.formula_version == 1


# --- ошибки ---------------------------------------------------------------


async def test_rate_limit_is_not_unprofitable(database: Database, clock: FakeClock) -> None:
    """429 не превращает возможность в убыточную (§55, §76.11)."""
    level2_adapters = {
        ProviderId.ONEINCH: FakeAdapter(ProviderId.ONEINCH, clock, error=RateLimitError("429")),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    amount = result.amount_results[0]
    assert amount.status is not AmountVerificationStatus.VERIFIED_UNPROFITABLE
    assert amount.status is AmountVerificationStatus.ROUTE_UNAVAILABLE
    assert result.job_status is not JobStatus.CONFIRMED


async def test_temporary_error_is_not_unprofitable(database: Database, clock: FakeClock) -> None:
    """Временная ошибка API — не признак убыточности (§53)."""
    level2_adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, error=MonikTimeoutError("provider timed out")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=level2_adapters)
    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is not AmountVerificationStatus.VERIFIED_UNPROFITABLE
    assert result.job_status is JobStatus.REJECTED


# --- expiration, идемпотентность, retry ----------------------------------


async def test_expired_opportunity_is_not_verified(database: Database, clock: FakeClock) -> None:
    """Просроченная возможность не проверяется (§26)."""
    harness = await build_level2(configured(), database, clock)
    calls_before = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    clock.advance(timedelta(hours=1))

    result = await harness.scanner.confirm(harness.job)

    assert result.amount_results[0].status is AmountVerificationStatus.EXPIRED
    assert result.job_status is JobStatus.EXPIRED
    calls_after = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    assert calls_after == calls_before, "просроченный Job не выполняет внешних запросов"


async def test_repeated_confirmation_is_idempotent(harness: Level2Harness) -> None:
    """Повторная обработка не создаёт второй бизнес-результат (§70)."""
    first = await harness.scanner.confirm(harness.job)
    calls = sum(len(adapter.quote_calls) for adapter in harness.adapters.values())
    second = await harness.scanner.confirm(harness.job)

    assert second.revision == first.revision
    assert second.job_status is first.job_status
    assert sum(len(adapter.quote_calls) for adapter in harness.adapters.values()) == calls


async def test_retry_creates_a_new_revision_inside_the_same_job(
    harness: Level2Harness,
) -> None:
    """Повтор — новая попытка внутри того же ``#K`` (§71)."""
    first = await harness.scanner.confirm(harness.job)
    stored = await harness.jobs.get(harness.job.k_id)
    assert stored is not None

    second = await harness.scanner.confirm(stored)
    assert second.k_id == first.k_id
    assert second.revision == first.revision + 1
    saved = await harness.jobs.load_confirmation(harness.job.k_id, second.revision)
    assert saved is not None


async def test_missing_opportunity_fails_the_job(harness: Level2Harness) -> None:
    """Job без Opportunity — нарушение целостности, а не результат проверки."""
    orphan = harness.job.replace(opportunity_id=f.OpportunityId.generate())
    with pytest.raises(DomainValidationError):
        await harness.scanner.confirm(orphan)


# --- отмена ---------------------------------------------------------------


async def test_cancelled_job_is_never_confirmed(database: Database, clock: FakeClock) -> None:
    """Отменённый Job не становится CONFIRMED (§28)."""
    gate = asyncio.Event()
    started = asyncio.Event()

    class _Blocking(FakeAdapter):
        async def get_quote(self, request: object) -> object:  # type: ignore[override]
            started.set()
            await gate.wait()
            return await super().get_quote(request)  # type: ignore[arg-type]

    blocking = {
        ProviderId.ONEINCH: _Blocking(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: _Blocking(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = await build_level2(configured(), database, clock, level2_adapter_set=blocking)
    task = asyncio.ensure_future(harness.scanner.confirm(harness.job))
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    gate.set()

    job = await harness.jobs.get(harness.job.k_id)
    assert job is not None
    assert job.status is not JobStatus.CONFIRMED
    assert job.status is JobStatus.CANCELLED
    opportunity = await harness.opportunities.get(harness.opportunity.opportunity_id)
    assert opportunity is not None and opportunity.status is OpportunityStatus.CANCELLED
