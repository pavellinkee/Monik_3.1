"""Сквозные сценарии Monik на детерминированных адаптерах.

Каждый сценарий проходит полный путь: Level 1 → Level 2 → Opportunity
Service → очередь доставки, на реальной SQLite и с фиксированным временем.
Внешние вызовы отсутствуют: провайдеры и Telegram заменены test
implementations (``CLAUDE.md`` §10).
"""

from __future__ import annotations

import copy
import pathlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from monik.app.lifecycle import Application, create_application
from monik.config import LoadedConfiguration, parse_configuration
from monik.domain.enums.lifecycle import (
    AmountVerificationStatus,
    JobStatus,
    NotificationStatus,
    OpportunityStatus,
    ScanStatus,
)
from monik.domain.enums.notifications import DeliveryErrorKind, DestinationKind
from monik.domain.enums.operations import OperationType, RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import RateLimitError
from monik.domain.errors import TimeoutError as MonikTimeoutError
from monik.infrastructure.db import Database
from monik.infrastructure.providers.contract import AggregatorAdapter, QuoteRequest
from monik.infrastructure.providers.fake import FakeAdapter
from monik.infrastructure.telegram import FakeTransport
from monik.services.notifications import DeliveryReceipt, NotificationDispatcher
from monik.services.observability import FakeClock
from tests import factories as f
from tests.component.level1.conftest import arbitrage_rule, level1_document
from tests.component.notifications.conftest import notification_env
from tests.unit.config.conftest import VALID_ENV

#: Прибыльная комбинация: BUY через 1inch, SELL через 0x.
PROFITABLE = {"oneinch": ("0.050", "20.00"), "zero_x": ("0.049", "20.30")}

#: Убыточная комбинация: разница не покрывает расходы.
UNPROFITABLE = {"oneinch": ("0.050", "20.00"), "zero_x": ("0.049", "20.02")}


def scenario_document(*, telegram: bool = False, **overrides: Any) -> dict[str, Any]:
    """Конфигурация сценария."""
    document = copy.deepcopy(level1_document())
    document["gas"] = {
        "sources": ["static"],
        "static_wei_per_gas": {"polygon": 5_000_000_000},
    }
    if telegram:
        document["notifications"] = {
            "enabled": True,
            "telegram": {
                "enabled": True,
                "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
                "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
                "commands_enabled": False,
            },
        }
    document.update(overrides)
    return document


def adapters_from(
    rates: dict[str, tuple[str, str]],
    clock: FakeClock,
    *,
    errors: dict[ProviderId, Exception] | None = None,
    fixed_route: dict[ProviderId, RouteValidationOutcome] | None = None,
) -> dict[ProviderId, AggregatorAdapter]:
    """Набор адаптеров с заданными курсами и поведением."""
    failures = errors or {}
    outcomes = fixed_route or {}
    built: dict[ProviderId, AggregatorAdapter] = {}
    for name, (buy, sell) in rates.items():
        provider = ProviderId(name)
        built[provider] = FakeAdapter(
            provider,
            clock,
            output_rule=arbitrage_rule(buy, sell),
            error=failures.get(provider),  # type: ignore[arg-type]
            fixed_route_outcome=outcomes.get(provider, RouteValidationOutcome.REPRODUCED),
        )
    return built


@dataclass
class Scenario:
    """Запущенное приложение сценария."""

    app: Application
    database: Database
    loaded: LoadedConfiguration
    clock: FakeClock

    @property
    def container(self) -> Any:
        return self.app.container


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


async def start_scenario(
    tmp_path: pathlib.Path,
    clock: FakeClock,
    *,
    rates: dict[str, tuple[str, str]] | None = None,
    document: dict[str, Any] | None = None,
    errors: dict[ProviderId, Exception] | None = None,
    fixed_route: dict[ProviderId, RouteValidationOutcome] | None = None,
    environ: dict[str, str] | None = None,
) -> Scenario:
    """Собрать и запустить приложение сценария."""
    config_document = document or scenario_document()
    config_document.setdefault("database", {})["path"] = str(tmp_path / "scenario.db")
    loaded = parse_configuration(config_document, environ=environ or dict(VALID_ENV))
    app, database = await create_application(
        loaded,
        clock=clock,
        adapters=adapters_from(rates or PROFITABLE, clock, errors=errors, fixed_route=fixed_route),
    )
    await app.startup()
    return Scenario(app=app, database=database, loaded=loaded, clock=clock)


@pytest.fixture
async def scenario(tmp_path: pathlib.Path, clock: FakeClock) -> AsyncIterator[Scenario]:
    started = await start_scenario(tmp_path, clock)
    try:
        yield started
    finally:
        await started.app.shutdown()
        await started.database.close()


async def confirm_all(scenario: Scenario) -> tuple[Any, ...]:
    """Выполнить цикл Level 1 и дождаться подтверждений Level 2."""
    result = await scenario.container.level1.scan()
    confirmations = await scenario.container.level2_worker.drain()
    return result, confirmations


# --- успешный сценарий ----------------------------------------------------


async def test_profitable_opportunity_end_to_end(scenario: Scenario) -> None:
    """Полный путь от поиска до постановки уведомления."""
    result, confirmations = await confirm_all(scenario)

    assert result.status is ScanStatus.COMPLETE
    assert len(result.opportunities) == 1
    assert confirmations[0].job_status is JobStatus.CONFIRMED

    outcome = await scenario.container.opportunities.record_confirmation(
        result.opportunities[0], confirmations[0]
    )
    assert outcome.status is OpportunityStatus.CONFIRMED
    assert outcome.snapshot.has_confirmed_amount


async def test_multiple_amounts_share_route_with_own_results(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Несколько сумм: один маршрут, отдельные результаты."""
    document = scenario_document()
    document["scanner"]["amounts"] = ["100", "500"]
    started = await start_scenario(tmp_path, clock, document=document)
    try:
        result, confirmations = await confirm_all(started)

        opportunity = result.opportunities[0]
        assert len(opportunity.amounts) == 2
        assert len(confirmations[0].amount_results) == 2
        first, second = confirmations[0].amount_results
        assert first.buy_quote is not None and second.buy_quote is not None
        assert first.buy_quote.route.fingerprint == second.buy_quote.route.fingerprint
        assert first.profit_result != second.profit_result
    finally:
        await started.app.shutdown()
        await started.database.close()


# --- отрицательные сценарии ----------------------------------------------


async def test_unprofitable_opportunity_is_not_created(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Кандидат ниже порога не становится Opportunity."""
    started = await start_scenario(tmp_path, clock, rates=UNPROFITABLE)
    try:
        result = await started.container.level1.scan()

        assert result.opportunities == ()
        assert await started.container.level2_worker.drain() == ()
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_provider_timeout_yields_partial_scan(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Таймаут одного провайдера не останавливает цикл."""
    started = await start_scenario(
        tmp_path,
        clock,
        errors={ProviderId.ZERO_X: MonikTimeoutError("provider timed out")},
    )
    try:
        result = await started.container.level1.scan()

        assert result.status is ScanStatus.PARTIAL
        assert result.opportunities == ()
        assert result.failures
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_rate_limit_is_not_unprofitable(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Rate limit фиксируется как сбой, а не как отсутствие прибыли."""
    started = await start_scenario(
        tmp_path, clock, errors={ProviderId.ONEINCH: RateLimitError("429")}
    )
    try:
        result = await started.container.level1.scan()

        assert result.opportunities == ()
        assert any(attempt.error_message == "429" for attempt in result.failures)
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_route_unavailable_is_not_unprofitable(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Level 2 не подменяет маршрут: несовпадение — отдельная причина."""
    started = await start_scenario(tmp_path, clock)
    try:
        result = await started.container.level1.scan()
        opportunity = result.opportunities[0]
        job = await started.container.repositories.jobs.get_by_opportunity(
            opportunity.opportunity_id
        )
        assert job is not None
        await started.container.level2_worker.drain()

        # Провайдер перестал воспроизводить исходный маршрут.
        started.container.adapters[ProviderId.ONEINCH] = FakeAdapter(
            ProviderId.ONEINCH,
            clock,
            output_rule=arbitrage_rule("0.050", "20.00"),
            fixed_route_outcome=RouteValidationOutcome.MISMATCH,
        )
        confirmation = await started.container.level2.confirm(
            await started.container.repositories.jobs.get(job.k_id)  # type: ignore[arg-type]
        )

        assert confirmation.amount_results[0].status is AmountVerificationStatus.ROUTE_UNAVAILABLE
        assert confirmation.job_status is JobStatus.REJECTED
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_expired_opportunity_is_not_confirmed(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Просроченная возможность не подтверждается."""
    started = await start_scenario(tmp_path, clock)
    try:
        result = await started.container.level1.scan()
        job = await started.container.repositories.jobs.get_by_opportunity(
            result.opportunities[0].opportunity_id
        )
        assert job is not None
        await started.container.level2_worker.drain()

        clock.advance(timedelta(hours=1))
        stored = await started.container.repositories.jobs.get(job.k_id)
        assert stored is not None
        confirmation = await started.container.level2.confirm(stored)

        assert confirmation.job_status is JobStatus.EXPIRED
    finally:
        await started.app.shutdown()
        await started.database.close()


# --- дедупликация ---------------------------------------------------------


async def test_repeated_scan_does_not_duplicate_opportunity(
    scenario: Scenario,
) -> None:
    """Тот же кандидат в окне дедупликации не создаёт вторую возможность."""
    first = await scenario.container.level1.scan()
    second = await scenario.container.level1.scan()

    assert len(first.opportunities) == 1
    assert second.opportunities == ()
    row = await scenario.database.fetch_one("SELECT COUNT(*) AS count FROM opportunities", ())
    assert row is not None and row["count"] == 1


async def test_confirmation_is_recorded_once(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Повторная фиксация подтверждения не создаёт вторую очередь доставки."""
    started = await start_scenario(
        tmp_path,
        clock,
        document=scenario_document(telegram=True),
        environ=notification_env(),
    )
    try:
        result, confirmations = await confirm_all(started)

        first = await started.container.opportunities.record_confirmation(
            result.opportunities[0], confirmations[0]
        )
        second = await started.container.opportunities.record_confirmation(
            result.opportunities[0], confirmations[0]
        )

        assert first.notifications and second.already_recorded
        assert len(first.notifications) == len(second.notifications)
        queued = await started.container.repositories.notifications.list_for_opportunity(
            result.opportunities[0].opportunity_id
        )
        assert len(queued) == 1
    finally:
        await started.app.shutdown()
        await started.database.close()


# --- доставка -------------------------------------------------------------


async def test_notification_delivery_and_failure(tmp_path: pathlib.Path, clock: FakeClock) -> None:
    """Доставка уведомления и её отказ не меняют подтверждение."""
    started = await start_scenario(
        tmp_path,
        clock,
        document=scenario_document(telegram=True),
        environ=notification_env(),
    )
    transport = FakeTransport(
        receipt=DeliveryReceipt(
            delivered=False, error_kind=DeliveryErrorKind.AUTH_ERROR, error_message="401"
        )
    )
    dispatcher = NotificationDispatcher(
        started.loaded.config.notifications,
        store=started.container.repositories.notifications,
        transports={DestinationKind.TELEGRAM.value: transport},
        clock=clock,
    )
    try:
        result, confirmations = await confirm_all(started)
        outcome = await started.container.opportunities.record_confirmation(
            result.opportunities[0], confirmations[0]
        )
        assert outcome.notifications

        report = await dispatcher.dispatch_pending()

        assert report.failed
        stored = await started.container.repositories.opportunities.get(
            result.opportunities[0].opportunity_id
        )
        assert stored is not None and stored.status is OpportunityStatus.CONFIRMED
        notification = await started.container.repositories.notifications.get(
            outcome.notifications[0].notification_id
        )
        assert notification is not None
        assert notification.status is NotificationStatus.FAILED
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_successful_delivery_carries_the_details_button(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Каждое уведомление содержит кнопку ``об`` (``CLAUDE.md`` §35)."""
    started = await start_scenario(
        tmp_path,
        clock,
        document=scenario_document(telegram=True),
        environ=notification_env(),
    )
    transport = FakeTransport()
    dispatcher = NotificationDispatcher(
        started.loaded.config.notifications,
        store=started.container.repositories.notifications,
        transports={DestinationKind.TELEGRAM.value: transport},
        clock=clock,
    )
    try:
        result, confirmations = await confirm_all(started)
        await started.container.opportunities.record_confirmation(
            result.opportunities[0], confirmations[0]
        )

        await dispatcher.dispatch_pending()

        assert transport.sent
        assert transport.sent[0].details_label == "об"
        assert str(confirmations[0].k_id) in transport.sent[0].text
    finally:
        await started.app.shutdown()
        await started.database.close()


# --- параллелизм ----------------------------------------------------------


async def test_scan_covers_every_configured_amount(
    tmp_path: pathlib.Path, clock: FakeClock
) -> None:
    """Каждая настроенная сумма получает собственные запросы."""
    document = scenario_document()
    document["scanner"]["amounts"] = ["100", "500"]
    started = await start_scenario(tmp_path, clock, document=document)
    try:
        await started.container.level1.scan()

        buys = [
            call
            for adapter in started.container.adapters.values()
            for call in adapter.quote_calls  # type: ignore[attr-defined]
            if call.operation is OperationType.BUY
        ]
        amounts = {call.input_amount.as_decimal for call in buys}
        assert amounts == {Decimal(100), Decimal(500)}
    finally:
        await started.app.shutdown()
        await started.database.close()


async def test_quote_requests_never_bypass_the_adapter(scenario: Scenario) -> None:
    """Все котировки получены через адаптеры (``CLAUDE.md`` §14)."""
    await scenario.container.level1.scan()

    calls = [
        call for adapter in scenario.container.adapters.values() for call in adapter.quote_calls
    ]
    assert calls
    assert all(isinstance(call, QuoteRequest) for call in calls)
