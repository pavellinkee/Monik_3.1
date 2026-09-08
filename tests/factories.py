"""Фабрики валидных доменных объектов для тестов.

Все значения детерминированы: тесты не должны зависеть от системного времени
или случайных данных (``23_TESTING.md`` §17-19).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from monik.domain.enums import (
    CalculationStatus,
    CostInclusion,
    FeeStatus,
    FeeType,
    JobStatus,
    OperationType,
    OpportunityStatus,
    ProviderId,
    RoutingMode,
    ThresholdMetric,
)
from monik.domain.models import (
    Candidate,
    ConversionRate,
    CostBreakdown,
    Fee,
    Gas,
    GasPrice,
    Level2Job,
    Opportunity,
    OpportunityAmount,
    ProfitCalculationInput,
    ProfitResult,
    Quote,
    Route,
    RouteSnapshot,
    RouteStep,
    ThresholdOutcome,
    Token,
    TokenKey,
)
from monik.domain.value_objects import (
    KId,
    NetworkId,
    OpportunityId,
    Percentage,
    RequestId,
    ScanId,
    VId,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
POLYGON = NetworkId("polygon")

USDT = Token(
    network_id=POLYGON,
    address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
    symbol="USDT",
    decimals=6,
)
AAVE = Token(
    network_id=POLYGON,
    address="0xD6DF932A45C0f255f85145f286eA0b292B21C90B",
    symbol="AAVE",
    decimals=18,
)
WMATIC = Token(
    network_id=POLYGON,
    address="0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    symbol="WMATIC",
    decimals=18,
)


def route(
    *,
    provider_id: ProviderId = ProviderId.ONEINCH,
    operation: OperationType = OperationType.BUY,
    input_token: TokenKey | None = None,
    output_token: TokenKey | None = None,
    routing_mode: RoutingMode = RoutingMode.CLASSIC,
    protocol: str = "quickswap_v3",
) -> Route:
    """Простой одношаговый маршрут."""
    source = input_token or USDT.key
    target = output_token or AAVE.key
    return Route(
        provider_id=provider_id,
        network_id=POLYGON,
        operation=operation,
        routing_mode=routing_mode,
        input_token=source,
        output_token=target,
        steps=(RouteStep(input_token=source, output_token=target, protocol=protocol),),
    )


def quote(
    *,
    operation: OperationType = OperationType.BUY,
    provider_id: ProviderId = ProviderId.ONEINCH,
    input_token: Token = USDT,
    output_token: Token = AAVE,
    input_raw: int = 100_000_000,
    output_raw: int = 5_140_000_000_000_000_000,
    created_at: datetime = NOW,
    routing_mode: RoutingMode = RoutingMode.CLASSIC,
) -> Quote:
    """Валидная нормализованная котировка."""
    quote_route = route(
        provider_id=provider_id,
        operation=operation,
        input_token=input_token.key,
        output_token=output_token.key,
        routing_mode=routing_mode,
    )
    return Quote(
        provider_id=provider_id,
        network_id=POLYGON,
        operation=operation,
        input_token=input_token.key,
        output_token=output_token.key,
        input_amount=input_token.amount_from_base_units(input_raw),
        output_amount=output_token.amount_from_base_units(output_raw),
        route=quote_route,
        created_at=created_at,
        request_id=RequestId("11111111-1111-4111-8111-111111111111"),
    )


def profit_result(
    *,
    status: CalculationStatus = CalculationStatus.COMPLETE,
    net_roi: str = "1.50",
    passed: bool = True,
    input_raw: int = 100_000_000,
    output_raw: int = 101_500_000,
) -> ProfitResult:
    """Результат расчёта прибыли."""
    complete = status is CalculationStatus.COMPLETE
    return ProfitResult(
        status=status,
        profit_currency=USDT.key,
        input_amount=USDT.amount_from_base_units(input_raw),
        final_output=USDT.amount_from_base_units(output_raw),
        gross_profit=Decimal("1.50") if complete else None,
        gross_roi=Percentage(value=Decimal("1.50")) if complete else None,
        costs=CostBreakdown(
            total_fees=Decimal("0"),
            gas_cost=Decimal("0"),
            other_costs=Decimal("0"),
            rebates=Decimal("0"),
        )
        if complete
        else None,
        net_profit=Decimal(net_roi) if complete else None,
        net_roi=Percentage(value=Decimal(net_roi)) if complete else None,
        threshold_outcome=ThresholdOutcome(
            metric=ThresholdMetric.NET_ROI,
            threshold=Decimal("1.00"),
            actual=Decimal(net_roi),
            passed=passed,
        )
        if complete
        else None,
        calculated_at=NOW,
    )


def candidate(*, created_at: datetime = NOW) -> Candidate:
    """Согласованный round-trip кандидат USDT -> AAVE -> USDT."""
    buy = quote(operation=OperationType.BUY, created_at=created_at)
    sell = Quote(
        provider_id=ProviderId.ZERO_X,
        network_id=POLYGON,
        operation=OperationType.SELL,
        input_token=AAVE.key,
        output_token=USDT.key,
        input_amount=buy.output_amount,
        output_amount=USDT.amount_from_base_units(101_500_000),
        route=route(
            provider_id=ProviderId.ZERO_X,
            operation=OperationType.SELL,
            input_token=AAVE.key,
            output_token=USDT.key,
        ),
        created_at=created_at,
        request_id=RequestId("22222222-2222-4222-8222-222222222222"),
    )
    return Candidate(
        scan_id=ScanId("33333333-3333-4333-8333-333333333333"),
        buy_quote=buy,
        sell_quote=sell,
        preliminary_result=profit_result(),
        detected_at=created_at,
    )


def route_snapshot() -> RouteSnapshot:
    """Пара маршрутов BUY/SELL для round-trip."""
    return candidate().route_snapshot


def opportunity_amount(*, input_raw: int = 100_000_000) -> OpportunityAmount:
    """Amount-контекст возможности."""
    return OpportunityAmount(
        input_amount=USDT.amount_from_base_units(input_raw),
        preliminary_result=profit_result(input_raw=input_raw),
        preliminary_buy_output=AAVE.amount_from_base_units(5_140_000_000_000_000_000),
        preliminary_sell_output=USDT.amount_from_base_units(101_500_000),
    )


def opportunity(
    *,
    status: OpportunityStatus = OpportunityStatus.CREATED,
    amounts: tuple[OpportunityAmount, ...] | None = None,
    detected_at: datetime = NOW,
    lifetime: timedelta = timedelta(minutes=5),
) -> Opportunity:
    """Возможность, созданная Level 1."""
    return Opportunity(
        opportunity_id=OpportunityId("44444444-4444-4444-8444-444444444444"),
        v_id=VId.from_sequence(1234),
        scan_id=ScanId("33333333-3333-4333-8333-333333333333"),
        status=status,
        buy_provider_id=ProviderId.ONEINCH,
        sell_provider_id=ProviderId.ZERO_X,
        routes=route_snapshot(),
        amounts=(opportunity_amount(),) if amounts is None else amounts,
        detected_at=detected_at,
        expires_at=detected_at + lifetime,
    )


def level2_job(*, status: JobStatus = JobStatus.QUEUED, created_at: datetime = NOW) -> Level2Job:
    """Level 2 Job для возможности."""
    return Level2Job(
        k_id=KId.from_sequence(1234),
        opportunity_id=OpportunityId("44444444-4444-4444-8444-444444444444"),
        status=status,
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=5),
    )


def known_fee(
    *,
    amount: str = "0.20",
    inclusion: CostInclusion = CostInclusion.NOT_INCLUDED,
) -> Fee:
    """Достоверно известная комиссия."""
    return Fee(
        fee_type=FeeType.AGGREGATOR,
        status=FeeStatus.KNOWN,
        amount=Decimal(amount),
        currency=USDT.key,
        inclusion=inclusion,
        source="test",
        observed_at=NOW,
    )


def unknown_fee() -> Fee:
    """Комиссия, значение которой неизвестно."""
    return Fee(
        fee_type=FeeType.PROTOCOL,
        status=FeeStatus.UNKNOWN,
        inclusion=CostInclusion.UNKNOWN,
        source="test",
        observed_at=NOW,
    )


def known_gas(*, cost_native: str = "0.03") -> Gas:
    """Достоверно известный gas."""
    return Gas(
        network_id=POLYGON,
        status=FeeStatus.KNOWN,
        gas_units=250_000,
        gas_price=GasPrice(
            network_id=POLYGON,
            wei_per_gas=120_000_000_000,
            source="test",
            observed_at=NOW,
        ),
        native_token=WMATIC.key,
        cost_native=Decimal(cost_native),
        observed_at=NOW,
        source="test",
    )


def unknown_gas() -> Gas:
    """Gas, значение которого неизвестно."""
    return Gas(
        network_id=POLYGON,
        status=FeeStatus.UNKNOWN,
        observed_at=NOW,
        source="test",
    )


def native_rate(*, rate: str = "0.50", expires_at: datetime | None = None) -> ConversionRate:
    """Курс native token сети в валюту расчёта (WMATIC -> USDT)."""
    return ConversionRate(
        from_token=WMATIC.key,
        to_token=USDT.key,
        rate=Decimal(rate),
        source="test",
        observed_at=NOW,
        expires_at=expires_at,
    )


def calculation_input(
    *,
    input_raw: int = 100_000_000,
    buy_output_raw: int = 5 * 10**18,
    sell_output_raw: int = 101_500_000,
    fees: tuple[Fee, ...] = (),
    gas: Gas | None = None,
    conversion_rates: tuple[ConversionRate, ...] = (),
    threshold: str = "1.00",
    threshold_metric: ThresholdMetric = ThresholdMetric.NET_ROI,
    formula_version: int = 1,
) -> ProfitCalculationInput:
    """Контекст расчёта USDT -> AAVE -> USDT на 100 USDT."""
    return ProfitCalculationInput(
        input_amount=USDT.amount_from_base_units(input_raw),
        input_token=USDT.key,
        buy_output=AAVE.amount_from_base_units(buy_output_raw),
        intermediate_token=AAVE.key,
        sell_output=USDT.amount_from_base_units(sell_output_raw),
        output_token=USDT.key,
        fees=fees,
        gas=gas,
        conversion_rates=conversion_rates,
        threshold=Decimal(threshold),
        threshold_metric=threshold_metric,
        formula_version=formula_version,
    )
