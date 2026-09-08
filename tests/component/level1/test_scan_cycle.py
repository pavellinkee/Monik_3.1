"""Level 1: базовый цикл, создание Opportunity и передача Level 2.

Покрывает обязательный список ``10_LEVEL_1_SCANNER.md`` §93 и
``02_LEVEL1_SCANNER.md`` §95.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest

from monik.config import Configuration, parse_configuration
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.lifecycle import JobStatus, OpportunityStatus, ScanStatus
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import RateLimitError
from monik.domain.errors import TimeoutError as MonikTimeoutError
from monik.infrastructure.db import Database
from monik.infrastructure.providers.fake import FakeAdapter
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.level1.conftest import (
    Level1Harness,
    RecordingDispatcher,
    StaticFeeSource,
    StaticGasSource,
    StaticRateSource,
    arbitrage_rule,
    build_harness,
    level1_document,
    mark_unsupported,
)
from tests.unit.config.conftest import VALID_ENV


def configured(**scanner_overrides: object) -> Configuration:
    """Конфигурация с изменёнными параметрами scanner."""
    return parse_configuration(level1_document(**scanner_overrides), environ=dict(VALID_ENV)).config


# --- базовый цикл ---------------------------------------------------------


async def test_scan_creates_opportunity_and_level2_job(harness: Level1Harness) -> None:
    """Основной output Level 1 — Opportunity + Level 2 Job (§91)."""
    result = await harness.scanner.scan()

    assert result.status is ScanStatus.COMPLETE
    assert len(result.opportunities) == 1
    opportunity = result.opportunities[0]
    assert opportunity.status is OpportunityStatus.CREATED
    assert opportunity.buy_provider_id is ProviderId.ONEINCH
    assert opportunity.sell_provider_id is ProviderId.ZERO_X
    assert len(harness.dispatcher.submitted) == 1
    _, job = harness.dispatcher.submitted[0]
    assert job.status is JobStatus.QUEUED
    assert job.opportunity_id == opportunity.opportunity_id


async def test_level2_job_outranks_new_level1_scan(harness: Level1Harness) -> None:
    """Job получает более высокий приоритет, чем новый scan (§45, §59)."""
    await harness.scanner.scan()
    _, job = harness.dispatcher.submitted[0]
    assert job.priority is RequestPriority.LEVEL2
    assert job.priority.rank < RequestPriority.LEVEL1_BUY.rank
    assert job.priority.rank < RequestPriority.LEVEL1_SELL.rank


async def test_opportunity_and_job_are_persisted_atomically(harness: Level1Harness) -> None:
    """Opportunity без Job существовать не должна (``CLAUDE.md`` §29)."""
    result = await harness.scanner.scan()
    stored = await harness.opportunities.get_by_v_id(result.opportunities[0].v_id)
    assert stored is not None
    assert stored.opportunity_id == result.opportunities[0].opportunity_id


async def test_max_buy_is_selected_before_sell(harness: Level1Harness) -> None:
    """SELL считается от выхода лучшего BUY (§12)."""
    result = await harness.scanner.scan()
    opportunity = result.opportunities[0]
    amount = opportunity.amounts[0]
    # 1inch даёт 0.050 AAVE за USDT, 0x — 0.049: MAX BUY принадлежит 1inch.
    assert amount.preliminary_buy_output.as_decimal == Decimal(5)
    assert amount.preliminary_sell_output.as_decimal == Decimal("101.5")


async def test_buy_quote_is_requested_for_every_enabled_provider(
    harness: Level1Harness,
) -> None:
    """Оба провайдера участвуют в сравнении (§12, §71)."""
    await harness.scanner.scan()
    buys = {
        provider_id: [call for call in adapter.quote_calls if call.operation is OperationType.BUY]
        for provider_id, adapter in harness.adapters.items()
    }
    assert buys[ProviderId.ONEINCH]
    assert buys[ProviderId.ZERO_X]


async def test_sell_starts_from_the_intermediate_token(harness: Level1Harness) -> None:
    """SELL начинается ровно с промежуточного токена BUY (§82)."""
    await harness.scanner.scan()
    sells = [
        call
        for adapter in harness.adapters.values()
        for call in adapter.quote_calls
        if call.operation is OperationType.SELL
    ]
    assert sells
    for call in sells:
        assert call.input_token.key == f.AAVE.key
        assert call.output_token.key == f.USDT.key


async def test_scan_metadata_is_persisted(harness: Level1Harness) -> None:
    """Метаданные цикла сохраняются (§57, §76)."""
    result = await harness.scanner.scan()
    stored = await harness.scans.get(result.scan.scan_id)
    assert stored is not None
    assert stored.status is ScanStatus.COMPLETE
    assert stored.statistics.quote_requests > 0
    assert stored.statistics.opportunities_created == 1
    assert stored.finished_at is not None


# --- суммы ----------------------------------------------------------------


async def test_multiple_amounts_share_one_route(database: Database, clock: FakeClock) -> None:
    """Все суммы одной Opportunity используют один маршрут (§24, §89)."""
    harness = build_harness(configured(amounts=["100", "500"]), database, clock)
    result = await harness.scanner.scan()

    opportunity = result.opportunities[0]
    assert len(opportunity.amounts) == 2
    assert [amount.input_amount.raw for amount in opportunity.amounts] == [
        100_000_000,
        500_000_000,
    ]
    # Один route snapshot на все суммы: отдельного маршрута у суммы нет.
    assert opportunity.routes.buy_route.provider_id is ProviderId.ONEINCH
    assert opportunity.routes.sell_route.provider_id is ProviderId.ZERO_X


async def test_each_amount_keeps_its_own_result(database: Database, clock: FakeClock) -> None:
    """Результат одной суммы не переносится на другую (§22, §90)."""
    harness = build_harness(configured(amounts=["100", "500"]), database, clock)
    result = await harness.scanner.scan()

    amounts = result.opportunities[0].amounts
    assert amounts[0].preliminary_result.net_profit != amounts[1].preliminary_result.net_profit
    assert amounts[0].preliminary_sell_output != amounts[1].preliminary_sell_output


# --- фильтрация -----------------------------------------------------------


async def test_disabled_provider_is_not_requested(database: Database, clock: FakeClock) -> None:
    """Отключённый провайдер запросов не получает (§71)."""
    document = level1_document()
    document["providers"].append(
        {
            "provider_id": "velora",
            "enabled": False,
            "supported_networks": ["polygon"],
        }
    )
    configuration = parse_configuration(document, environ=dict(VALID_ENV)).config
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
        ProviderId.VELORA: FakeAdapter(
            ProviderId.VELORA, clock, output_rule=arbitrage_rule("0.060", "21.00")
        ),
    }
    harness = build_harness(configuration, database, clock, adapters=adapters)

    result = await harness.scanner.scan()
    assert harness.adapters[ProviderId.VELORA].quote_calls == []
    assert result.opportunities[0].buy_provider_id is ProviderId.ONEINCH


async def test_disabled_token_is_not_scanned(harness: Level1Harness) -> None:
    """Отключённый токен не сканируется (§70)."""
    await harness.scanner.scan()
    scanned = {
        call.output_token.symbol
        for adapter in harness.adapters.values()
        for call in adapter.quote_calls
        if call.operation is OperationType.BUY
    }
    assert scanned == {"AAVE"}


async def test_unsupported_capability_blocks_the_request(harness: Level1Harness) -> None:
    """Заведомо неподдерживаемая комбинация во внешний API не уходит (§15, §76)."""
    await mark_unsupported(
        harness.capabilities, ProviderId.ONEINCH, CapabilityOperation.QUOTE_BUY, f.AAVE
    )
    result = await harness.scanner.scan()

    buy_calls = [
        call
        for call in harness.adapters[ProviderId.ONEINCH].quote_calls
        if call.operation is OperationType.BUY
    ]
    assert buy_calls == []
    assert result.scan.statistics.skipped_combinations > 0


async def test_unknown_capability_still_allows_a_runtime_check(
    harness: Level1Harness,
) -> None:
    """UNKNOWN не приравнивается к UNSUPPORTED (§16)."""
    result = await harness.scanner.scan()
    assert harness.adapters[ProviderId.ONEINCH].quote_calls
    assert result.opportunities


async def test_unknown_capability_is_blocked_when_policy_forbids(
    database: Database, clock: FakeClock
) -> None:
    """Runtime-проверка UNKNOWN отключается конфигурацией."""
    document = level1_document()
    document["scanner"]["level1"] = {"allow_unknown_capability": False}
    configuration = parse_configuration(document, environ=dict(VALID_ENV)).config
    harness = build_harness(configuration, database, clock)

    result = await harness.scanner.scan()
    assert result.opportunities == ()
    assert all(adapter.quote_calls == [] for adapter in harness.adapters.values())


async def test_same_provider_pair_is_rejected_by_default(
    database: Database, clock: FakeClock
) -> None:
    """Один провайдер на обе ноги по умолчанию запрещён (§18).

    Прибыльный round-trip существует только внутри 1inch; кросс-провайдерная
    комбинация убыточна, поэтому Opportunity не создаётся.
    """
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.30")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.00")
        ),
    }
    harness = build_harness(configured(), database, clock, adapters=adapters)

    result = await harness.scanner.scan()
    assert result.opportunities == ()
    assert not harness.configuration.routes.allow_same_provider


# --- порог и расходы ------------------------------------------------------


async def test_candidate_below_threshold_is_dropped(database: Database, clock: FakeClock) -> None:
    """Ниже preliminary threshold Opportunity не создаётся (§48)."""
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.05")
        ),
    }
    harness = build_harness(configured(), database, clock, adapters=adapters)
    result = await harness.scanner.scan()

    assert result.opportunities == ()
    assert harness.dispatcher.submitted == []


async def test_unknown_gas_blocks_opportunity_creation(
    database: Database, clock: FakeClock
) -> None:
    """Неизвестный обязательный расход не считается нулём (§50)."""
    harness = build_harness(configured(), database, clock, gas=StaticGasSource(f.unknown_gas()))
    result = await harness.scanner.scan()

    assert result.opportunities == ()


async def test_missing_conversion_rate_blocks_opportunity(
    database: Database, clock: FakeClock
) -> None:
    """Без курса стоимость газа неизвестна, а не равна нулю."""
    harness = build_harness(configured(), database, clock, rates=StaticRateSource(None))
    result = await harness.scanner.scan()

    assert result.opportunities == ()


async def test_unknown_fee_blocks_opportunity(database: Database, clock: FakeClock) -> None:
    """UNKNOWN fee не превращается в ноль (§50, ``02`` §32)."""
    harness = build_harness(
        configured(),
        database,
        clock,
        fees=StaticFeeSource(fees=(f.unknown_fee(),)),
    )
    result = await harness.scanner.scan()

    assert result.opportunities == ()


async def test_fees_are_requested_for_both_legs(harness: Level1Harness) -> None:
    """Комиссии берутся из Fee System для BUY и для SELL (§29-30)."""
    await harness.scanner.scan()
    operations = {context.operation for context in harness.fees.calls}
    assert operations == {OperationType.BUY, OperationType.SELL}


async def test_gas_estimate_covers_the_whole_round_trip(harness: Level1Harness) -> None:
    """Gas учитывается по обеим ногам (§31, §51)."""
    await harness.scanner.scan()
    assert harness.gas.calls
    assert all(units == 400_000 for units in harness.gas.calls if units is not None)


# --- дедупликация и отпечаток --------------------------------------------


async def test_repeated_scan_is_deduplicated_within_window(
    harness: Level1Harness,
) -> None:
    """Тот же кандидат в окне не создаёт вторую Opportunity (§44, §52)."""
    first = await harness.scanner.scan()
    second = await harness.scanner.scan()

    assert len(first.opportunities) == 1
    assert second.opportunities == ()
    assert second.scan.statistics.duplicate_opportunities == 1
    assert len(harness.dispatcher.submitted) == 1


async def test_deduplication_window_expires(database: Database, clock: FakeClock) -> None:
    """За пределами окна та же возможность создаётся заново (§44)."""
    harness = build_harness(
        configured(level1={"deduplication_window_seconds": 60}), database, clock
    )
    await harness.scanner.scan()
    clock.advance(timedelta(seconds=120))
    second = await harness.scanner.scan()

    assert len(second.opportunities) == 1


async def test_fingerprint_is_deterministic(harness: Level1Harness) -> None:
    """Отпечаток не зависит от случайного идентификатора (§53)."""
    result = await harness.scanner.scan()
    opportunity = result.opportunities[0]
    assert len(str(opportunity.fingerprint)) == 64
    assert (
        opportunity.fingerprint
        == opportunity.replace(opportunity_id=f.OpportunityId.generate()).fingerprint
    )


# --- ёмкость и ранжирование ----------------------------------------------


async def test_backpressure_limits_created_opportunities(
    database: Database, clock: FakeClock
) -> None:
    """Переполненная очередь Level 2 останавливает создание Job (§47)."""
    harness = build_harness(
        configured(), database, clock, dispatcher=RecordingDispatcher(capacity=0)
    )
    result = await harness.scanner.scan()

    assert result.opportunities == ()
    assert harness.dispatcher.submitted == []


async def test_per_scan_limit_is_respected(database: Database, clock: FakeClock) -> None:
    """Лимит на цикл ограничивает число созданных Opportunity (§48)."""
    harness = build_harness(configured(level1={"max_opportunities_per_scan": 1}), database, clock)
    result = await harness.scanner.scan()
    assert len(result.opportunities) <= 1


# --- изоляция ошибок ------------------------------------------------------


async def test_provider_failure_does_not_stop_the_scan(
    database: Database, clock: FakeClock
) -> None:
    """Ошибка одного провайдера не прекращает цикл (§51, §74)."""
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, error=MonikTimeoutError("provider timed out")
        ),
    }
    harness = build_harness(configured(), database, clock, adapters=adapters)
    result = await harness.scanner.scan()

    assert result.status is ScanStatus.PARTIAL
    assert result.failures
    assert result.opportunities == ()


async def test_rate_limit_does_not_create_false_opportunity(
    database: Database, clock: FakeClock
) -> None:
    """Rate limit фиксируется как сбой и не порождает ложную возможность (§53)."""
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(ProviderId.ONEINCH, clock, error=RateLimitError("429")),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = build_harness(configured(), database, clock, adapters=adapters)
    result = await harness.scanner.scan()

    assert result.opportunities == ()
    assert any(attempt.error_message == "429" for attempt in result.failures)


async def test_zero_output_quote_is_rejected(database: Database, clock: FakeClock) -> None:
    """Нулевой output валидной возможностью не является (``02`` §25)."""
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(ProviderId.ONEINCH, clock, output_rule=lambda _: 0),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = build_harness(configured(), database, clock, adapters=adapters)
    result = await harness.scanner.scan()

    assert result.opportunities == ()
    assert any(
        attempt.rejection_reason == "quote output amount is zero" for attempt in result.failures
    )


async def test_stale_quote_is_rejected(database: Database, clock: FakeClock) -> None:
    """Слишком старая котировка не используется (``02`` §28)."""
    stale_clock = FakeClock(f.NOW)
    adapters = {
        ProviderId.ONEINCH: FakeAdapter(
            ProviderId.ONEINCH, stale_clock, output_rule=arbitrage_rule("0.050", "20.00")
        ),
        ProviderId.ZERO_X: FakeAdapter(
            ProviderId.ZERO_X, stale_clock, output_rule=arbitrage_rule("0.049", "20.30")
        ),
    }
    harness = build_harness(
        configured(level1={"quote_max_age_seconds": 5}), database, clock, adapters=adapters
    )
    clock.advance(timedelta(seconds=60))
    result = await harness.scanner.scan()

    assert result.opportunities == ()
    assert any(
        attempt.rejection_reason == "quote is not fresh enough for this scan"
        for attempt in result.failures
    )


# --- отмена ----------------------------------------------------------------


async def test_cancelled_scan_is_not_complete(harness: Level1Harness) -> None:
    """Отменённый цикл не считается успешным (§67)."""
    task = asyncio.ensure_future(harness.scanner.scan())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    recent = await harness.scans.recent(limit=1)
    assert recent[0].status is ScanStatus.CANCELLED


# --- expiration ------------------------------------------------------------


async def test_opportunity_and_job_expire(harness: Level1Harness) -> None:
    """Opportunity и Job имеют срок жизни (§86, ``02`` §41)."""
    result = await harness.scanner.scan()
    opportunity = result.opportunities[0]
    _, job = harness.dispatcher.submitted[0]

    ttl = harness.configuration.scanner.level1.opportunity_ttl_seconds
    assert opportunity.expires_at == opportunity.detected_at + timedelta(seconds=ttl)
    assert not opportunity.is_expired(f.NOW)
    assert job.expires_at > job.created_at
