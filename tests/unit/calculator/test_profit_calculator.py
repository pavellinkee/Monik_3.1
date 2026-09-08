"""Profit Calculator: формулы, статусы, порог и защита от двойного учёта.

Покрывает обязательный список проверок ``09_PROFIT_CALCULATOR.md`` §77.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from monik.domain.enums import (
    CalculationStatus,
    CostInclusion,
    FeeStatus,
    FeeType,
    ThresholdMetric,
)
from monik.domain.models import ConversionRate, Fee, Gas, GasPrice, TokenKey
from monik.domain.value_objects import NetworkId
from monik.services.calculator import ProfitCalculator
from monik.services.observability import FakeClock
from tests import factories as f


@dataclass(frozen=True)
class _Case:
    """Ожидаемые значения одного расчёта."""

    gross_profit: str
    net_profit: str


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(f.NOW)


@pytest.fixture
def calculator(clock: FakeClock) -> ProfitCalculator:
    return ProfitCalculator(clock)


def _fee(
    *,
    fee_type: FeeType = FeeType.AGGREGATOR,
    amount: str = "0.20",
    inclusion: CostInclusion = CostInclusion.NOT_INCLUDED,
) -> Fee:
    return Fee(
        fee_type=fee_type,
        status=FeeStatus.KNOWN,
        amount=Decimal(amount),
        currency=f.USDT.key,
        inclusion=inclusion,
        source="test",
        observed_at=f.NOW,
    )


# --- gross ----------------------------------------------------------------


def test_gross_profit_is_final_output_minus_input(calculator: ProfitCalculator) -> None:
    """``gross_profit = final_output − input_amount`` (§9)."""
    result = calculator.calculate(f.calculation_input(gas=f.known_gas(), conversion_rates=()))
    assert result.gross_profit == Decimal("1.5")


def test_gross_roi_is_percentage_of_input(calculator: ProfitCalculator) -> None:
    """``gross_roi = gross_profit / input × 100`` (§10)."""
    result = calculator.calculate(f.calculation_input())
    assert result.gross_roi is not None
    assert result.gross_roi.value == Decimal("1.5")


def test_zero_profit_is_reported_as_zero(calculator: ProfitCalculator) -> None:
    """Нулевая прибыльность считается нулевой, а не убыточной (§23)."""
    data = f.calculation_input(sell_output_raw=100_000_000)
    result = calculator.calculate(data)
    assert result.gross_profit == Decimal(0)
    assert result.gross_roi is not None
    assert result.gross_roi.value == Decimal(0)


def test_negative_profit_is_not_clamped_to_zero(calculator: ProfitCalculator) -> None:
    """Убыток сохраняется как отрицательное значение (§22)."""
    data = f.calculation_input(sell_output_raw=98_000_000)
    result = calculator.calculate(data)
    assert result.gross_profit == Decimal("-2")
    assert result.net_profit is not None
    assert result.net_profit < 0


# --- costs ----------------------------------------------------------------


def test_net_profit_subtracts_all_known_costs(calculator: ProfitCalculator) -> None:
    """``net_profit = gross_profit − total_costs`` (§14)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20"), _fee(fee_type=FeeType.PROTOCOL, amount="0.10")),
        gas=f.known_gas(cost_native="0.03"),
        conversion_rates=(f.native_rate(rate="0.50"),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.total_fees == Decimal("0.30")
    assert result.costs.gas_cost == Decimal("0.015")
    assert result.net_profit == Decimal("1.185")


def test_rebate_is_a_separate_component(calculator: ProfitCalculator) -> None:
    """Rebate уменьшает стоимость и не смешивается с комиссией (§15)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20"), _fee(fee_type=FeeType.REBATE, amount="0.05")),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.total_fees == Decimal("0.20")
    assert result.costs.rebates == Decimal("0.05")
    assert result.costs.total_costs == Decimal("0.165")


def test_other_costs_are_tracked_separately(calculator: ProfitCalculator) -> None:
    """``other`` не растворяется в комиссиях агрегатора (§62)."""
    data = f.calculation_input(
        fees=(_fee(fee_type=FeeType.OTHER, amount="0.07"),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.total_fees == Decimal(0)
    assert result.costs.other_costs == Decimal("0.07")


def test_breakdown_reconstructs_net_profit(calculator: ProfitCalculator) -> None:
    """По разбивке можно восстановить итог — пример из §33 (§69)."""
    data = f.calculation_input(
        sell_output_raw=101_800_000,
        fees=(
            _fee(amount="0.20"),
            _fee(fee_type=FeeType.PROTOCOL, amount="0.10"),
            _fee(fee_type=FeeType.REBATE, amount="0.05"),
        ),
        gas=f.known_gas(cost_native="0.60"),
        conversion_rates=(f.native_rate(rate="0.50"),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None and result.gross_profit is not None
    restored = result.gross_profit - result.costs.total_costs
    assert restored == result.net_profit
    assert result.net_profit == Decimal("1.25")


# --- двойной учёт ---------------------------------------------------------


def test_fee_included_in_quote_is_not_subtracted_twice(calculator: ProfitCalculator) -> None:
    """Комиссия, уже отражённая в quote, повторно не вычитается (§44-45)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20", inclusion=CostInclusion.INCLUDED_IN_QUOTE),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.total_fees == Decimal(0)
    assert result.status is CalculationStatus.COMPLETE


def test_gas_included_in_quote_is_not_subtracted_twice(calculator: ProfitCalculator) -> None:
    """Gas, уже учтённый в исходном значении, не вычитается повторно (§46)."""
    gas = f.known_gas().replace(inclusion=CostInclusion.INCLUDED_IN_QUOTE)
    data = f.calculation_input(gas=gas, conversion_rates=(f.native_rate(),))
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.gas_cost == Decimal(0)
    assert result.status is CalculationStatus.COMPLETE


def test_unknown_inclusion_blocks_complete_status(calculator: ProfitCalculator) -> None:
    """Неизвестная включённость не позволяет считать расчёт полным (§45)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20", inclusion=CostInclusion.UNKNOWN),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert "fee[0]:aggregator:inclusion" in result.costs.unknown_components
    # Консервативно вычитается, чтобы прибыльность не оказалась завышенной.
    assert result.costs.total_fees == Decimal("0.20")


# --- неизвестные расходы --------------------------------------------------


def test_unknown_fee_is_not_zero(calculator: ProfitCalculator) -> None:
    """UNKNOWN fee не превращается в ноль (§16, §42)."""
    data = f.calculation_input(
        fees=(f.unknown_fee(),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert result.costs.unknown_components == ("fee[0]:protocol",)


def test_unknown_gas_is_not_zero(calculator: ProfitCalculator) -> None:
    """UNKNOWN gas не превращается в ноль (§16, §43)."""
    data = f.calculation_input(gas=f.unknown_gas())
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert result.costs.gas_cost == Decimal(0)
    assert "gas" in result.costs.unknown_components


def test_missing_gas_is_unknown_not_free(calculator: ProfitCalculator) -> None:
    """Отсутствие gas в контексте — неизвестный расход, а не его отсутствие."""
    result = calculator.calculate(f.calculation_input(gas=None))
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert "gas" in result.costs.unknown_components


def test_expired_fee_is_treated_as_unknown(calculator: ProfitCalculator, clock: FakeClock) -> None:
    """Просроченная комиссия не используется как достоверная (§42)."""
    fee = _fee(amount="0.20").replace(expires_at=f.NOW.replace(hour=13))
    clock.set_to(f.NOW.replace(hour=14))
    data = f.calculation_input(fees=(fee,), gas=f.known_gas(), conversion_rates=(f.native_rate(),))
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert result.costs.total_fees == Decimal(0)
    assert "fee[0]:aggregator" in result.costs.unknown_components


def test_confirmed_absence_of_fee_is_zero_and_complete(calculator: ProfitCalculator) -> None:
    """KNOWN с нулевой суммой — подтверждённое отсутствие комиссии."""
    data = f.calculation_input(
        fees=(_fee(amount="0"),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.COMPLETE
    assert result.costs is not None
    assert result.costs.unknown_components == ()


# --- конверсия ------------------------------------------------------------


def test_gas_is_converted_into_calculation_currency(calculator: ProfitCalculator) -> None:
    """Gas в native token переводится в валюту расчёта (§13)."""
    data = f.calculation_input(
        gas=f.known_gas(cost_native="0.03"),
        conversion_rates=(f.native_rate(rate="0.50"),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.gas_cost == Decimal("0.015")


def test_missing_conversion_makes_gas_unknown(calculator: ProfitCalculator) -> None:
    """Без курса стоимость газа не выдумывается (§37)."""
    data = f.calculation_input(gas=f.known_gas(), conversion_rates=())
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert result.costs.gas_cost == Decimal(0)
    assert "gas:conversion" in result.costs.unknown_components


def test_stale_conversion_rate_is_not_used(calculator: ProfitCalculator, clock: FakeClock) -> None:
    """Устаревший курс не применяется бесконечно (§36)."""
    rate = f.native_rate(expires_at=f.NOW.replace(hour=13))
    clock.set_to(f.NOW.replace(hour=14))
    data = f.calculation_input(gas=f.known_gas(), conversion_rates=(rate,))
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.PARTIAL
    assert result.costs is not None
    assert "gas:conversion" in result.costs.unknown_components


def test_reverse_direction_rate_is_not_used_implicitly(calculator: ProfitCalculator) -> None:
    """``USDT -> WMATIC`` не подменяет ``WMATIC -> USDT`` (§38)."""
    inverse = ConversionRate(
        from_token=f.USDT.key,
        to_token=f.WMATIC.key,
        rate=Decimal(2),
        source="test",
        observed_at=f.NOW,
    )
    data = f.calculation_input(gas=f.known_gas(), conversion_rates=(inverse,))
    result = calculator.calculate(data)
    assert result.costs is not None
    assert "gas:conversion" in result.costs.unknown_components


def test_same_currency_needs_no_conversion(calculator: ProfitCalculator) -> None:
    """Одинаковые валюты не требуют курса (§34)."""
    data = f.calculation_input(fees=(_fee(amount="0.20"),), gas=None)
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.total_fees == Decimal("0.20")


# --- порог ----------------------------------------------------------------


def test_threshold_boundary_passes(calculator: ProfitCalculator) -> None:
    """Ровно пороговое значение проходит: сравнение ``>=`` (§26)."""
    data = f.calculation_input(
        sell_output_raw=101_000_000,
        gas=f.known_gas(cost_native="0"),
        conversion_rates=(f.native_rate(),),
        threshold="1.00",
    )
    result = calculator.calculate(data)
    assert result.net_roi is not None
    assert result.net_roi.value == Decimal(1)
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.passed is True


def test_threshold_just_below_fails(calculator: ProfitCalculator) -> None:
    """Значение ниже порога не проходит."""
    data = f.calculation_input(
        sell_output_raw=100_999_999,
        gas=f.known_gas(cost_native="0"),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.passed is False


def test_unknown_cost_blocks_threshold(calculator: ProfitCalculator) -> None:
    """Неизвестный расход не позволяет подтвердить прохождение порога (§27)."""
    data = f.calculation_input(sell_output_raw=101_200_000, gas=f.unknown_gas())
    result = calculator.calculate(data)
    assert result.net_roi is not None
    assert result.net_roi.value == Decimal("1.2")
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.passed is False
    assert result.threshold_outcome.blocked_by_unknown_cost is True
    assert result.is_profitable is False


def test_threshold_is_taken_from_input_not_hardcoded(calculator: ProfitCalculator) -> None:
    """Порог приходит из конфигурации через входную модель (§24, §51)."""
    data = f.calculation_input(
        gas=f.known_gas(cost_native="0"),
        conversion_rates=(f.native_rate(),),
        threshold="2.00",
    )
    result = calculator.calculate(data)
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.threshold == Decimal("2.00")
    assert result.threshold_outcome.passed is False


def test_gross_roi_metric_is_not_blocked_by_unknown_costs(calculator: ProfitCalculator) -> None:
    """Неизвестный расход не влияет на gross-метрику."""
    data = f.calculation_input(
        gas=f.unknown_gas(),
        threshold_metric=ThresholdMetric.GROSS_ROI,
        threshold="1.00",
    )
    result = calculator.calculate(data)
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.metric is ThresholdMetric.GROSS_ROI
    assert result.threshold_outcome.actual == Decimal("1.5")
    assert result.threshold_outcome.passed is True
    # Полным расчёт всё равно не является: net-результат недостоверен.
    assert result.status is CalculationStatus.PARTIAL
    assert result.is_profitable is False


def test_net_profit_metric_is_supported(calculator: ProfitCalculator) -> None:
    """Порог может применяться к абсолютной прибыли (§50)."""
    data = f.calculation_input(
        gas=f.known_gas(cost_native="0"),
        conversion_rates=(f.native_rate(),),
        threshold_metric=ThresholdMetric.NET_PROFIT,
        threshold="1.00",
    )
    result = calculator.calculate(data)
    assert result.threshold_outcome is not None
    assert result.threshold_outcome.actual == Decimal("1.5")
    assert result.threshold_outcome.passed is True


# --- статусы --------------------------------------------------------------


def test_complete_status_requires_all_known(calculator: ProfitCalculator) -> None:
    data = f.calculation_input(
        fees=(_fee(amount="0.20"),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.COMPLETE
    assert result.is_profitable is True


def test_invalid_formula_version_is_rejected(calculator: ProfitCalculator) -> None:
    """Старый результат нельзя интерпретировать новой формулой (§68)."""
    result = calculator.calculate(f.calculation_input(formula_version=2))
    assert result.status is CalculationStatus.INVALID
    assert result.invalid_reason is not None
    assert result.net_profit is None


def test_impossible_buy_output_is_invalid(calculator: ProfitCalculator) -> None:
    """Нулевой BUY output противоречит контексту (§20, §41)."""
    result = calculator.calculate(f.calculation_input(buy_output_raw=0))
    assert result.status is CalculationStatus.INVALID
    assert result.invalid_reason == "buy output must be positive"


def test_impossible_final_output_is_invalid(calculator: ProfitCalculator) -> None:
    result = calculator.calculate(f.calculation_input(sell_output_raw=0))
    assert result.status is CalculationStatus.INVALID
    assert result.invalid_reason == "final output must be positive"


def test_fee_from_another_network_is_invalid(calculator: ProfitCalculator) -> None:
    """Комиссия в валюте другой сети — противоречие данных (§20)."""
    foreign = _fee().replace(
        currency=TokenKey(network_id=NetworkId("ethereum"), address=f.USDT.address),
    )
    result = calculator.calculate(f.calculation_input(fees=(foreign,)))
    assert result.status is CalculationStatus.INVALID
    assert result.invalid_reason is not None
    assert "network ethereum" in result.invalid_reason


def test_unknown_status_when_final_output_cannot_be_expressed(
    calculator: ProfitCalculator,
) -> None:
    """Без валюты результата расчёт невозможен (§21, §64)."""
    data = f.calculation_input().replace(output_token=f.AAVE.key)
    result = calculator.calculate(data)
    assert result.status is CalculationStatus.UNKNOWN
    assert result.gross_profit is None
    assert result.net_profit is None


def test_result_carries_formula_version_and_timestamp(
    calculator: ProfitCalculator,
) -> None:
    result = calculator.calculate(f.calculation_input(gas=f.unknown_gas()))
    assert result.formula_version == 1
    assert result.calculated_at == f.NOW
    assert result.profit_currency == f.USDT.key


# --- детерминизм и точность ----------------------------------------------


def test_calculation_is_deterministic(calculator: ProfitCalculator) -> None:
    """Одинаковые входные данные дают одинаковый результат (§49, §71)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20"),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    assert calculator.calculate(data) == calculator.calculate(data)


def test_precision_is_independent_of_ambient_context(calculator: ProfitCalculator) -> None:
    """Результат не зависит от глобального decimal-контекста (§39, §49)."""
    import decimal

    data = f.calculation_input(
        sell_output_raw=101_333_333,
        gas=f.known_gas(cost_native="0.037"),
        conversion_rates=(f.native_rate(rate="0.333333"),),
    )
    baseline = calculator.calculate(data)
    with decimal.localcontext() as ctx:
        ctx.prec = 6
        narrowed = calculator.calculate(data)
    assert narrowed == baseline


def test_intermediate_values_are_not_rounded(calculator: ProfitCalculator) -> None:
    """Промежуточные значения не округляются ради отображения (§39-40)."""
    data = f.calculation_input(
        gas=f.known_gas(cost_native="0.0000001"),
        conversion_rates=(f.native_rate(rate="0.5"),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    assert result.costs.gas_cost == Decimal("0.00000005")


def test_more_costs_never_increase_net_profit(calculator: ProfitCalculator) -> None:
    """Инвариант: рост расходов не повышает прибыль (§78)."""
    rates = (f.native_rate(),)
    cheap = calculator.calculate(
        f.calculation_input(fees=(_fee(amount="0.10"),), gas=f.known_gas(), conversion_rates=rates)
    )
    expensive = calculator.calculate(
        f.calculation_input(fees=(_fee(amount="0.40"),), gas=f.known_gas(), conversion_rates=rates)
    )
    assert cheap.net_profit is not None and expensive.net_profit is not None
    assert expensive.net_profit < cheap.net_profit


def test_each_amount_is_calculated_independently(calculator: ProfitCalculator) -> None:
    """Результат одной суммы не переносится на другую (§53-54)."""
    rates = (f.native_rate(),)
    small = calculator.calculate(
        f.calculation_input(
            input_raw=50_000_000,
            sell_output_raw=50_750_000,
            gas=f.known_gas(cost_native="0.03"),
            conversion_rates=rates,
        )
    )
    large = calculator.calculate(
        f.calculation_input(
            input_raw=1_000_000_000,
            sell_output_raw=1_015_000_000,
            gas=f.known_gas(cost_native="0.03"),
            conversion_rates=rates,
        )
    )
    assert small.net_profit != large.net_profit
    assert small.net_roi is not None and large.net_roi is not None
    assert small.net_roi.value != large.net_roi.value


def test_calculator_uses_no_float(calculator: ProfitCalculator) -> None:
    """Все финансовые значения результата — точные (§3)."""
    data = f.calculation_input(
        fees=(_fee(amount="0.20"),),
        gas=f.known_gas(),
        conversion_rates=(f.native_rate(),),
    )
    result = calculator.calculate(data)
    assert result.costs is not None
    values = (
        result.gross_profit,
        result.net_profit,
        result.costs.total_fees,
        result.costs.gas_cost,
        result.costs.rebates,
    )
    assert all(isinstance(value, Decimal) for value in values)


def test_gas_price_components_are_integers() -> None:
    """Raw blockchain amounts остаются целыми (§4)."""
    price = GasPrice(
        network_id=f.POLYGON,
        wei_per_gas=120_000_000_000,
        source="test",
        observed_at=f.NOW,
    )
    gas = Gas(
        network_id=f.POLYGON,
        status=FeeStatus.KNOWN,
        gas_units=250_000,
        gas_price=price,
        native_token=f.WMATIC.key,
        cost_native=Decimal("0.03"),
        observed_at=f.NOW,
        source="test",
    )
    assert isinstance(gas.gas_units, int)
    assert isinstance(price.wei_per_gas, int)
