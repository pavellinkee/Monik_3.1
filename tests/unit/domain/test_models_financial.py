"""Тесты финансовых моделей: комиссии, gas, конверсия, результат расчёта.

Ключевые инварианты: UNKNOWN никогда не равен нулю, двойной учёт исключён,
неполный расчёт не считается подтверждением прибыльности.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from monik.domain.enums import (
    CalculationStatus,
    CostInclusion,
    FeeStatus,
    FeeType,
    ThresholdMetric,
)
from monik.domain.models import (
    ConversionRate,
    CostBreakdown,
    Fee,
    FeeSnapshot,
    Gas,
    GasPrice,
    ProfitCalculationInput,
    ThresholdOutcome,
)
from monik.domain.models.profit import PROFIT_FORMULA_VERSION
from tests import factories as f


class TestFee:
    def test_known_fee_carries_amount_and_currency(self) -> None:
        fee = f.known_fee(amount="0.25")
        assert fee.is_known
        assert fee.known_amount == Decimal("0.25")

    def test_unknown_fee_has_no_amount(self) -> None:
        """UNKNOWN fee не равна нулю (CLAUDE.md §23, 07 §15)."""
        fee = f.unknown_fee()
        assert not fee.is_known
        assert fee.amount is None
        with pytest.raises(ValueError, match="no known amount"):
            _ = fee.known_amount

    def test_unknown_fee_cannot_carry_amount(self) -> None:
        with pytest.raises(ValidationError, match="not zero"):
            Fee(
                fee_type=FeeType.PROTOCOL,
                status=FeeStatus.UNKNOWN,
                amount=Decimal("0"),
                currency=f.USDT.key,
                source="test",
                observed_at=f.NOW,
            )

    def test_known_fee_requires_amount(self) -> None:
        with pytest.raises(ValidationError, match="must carry an amount"):
            Fee(
                fee_type=FeeType.AGGREGATOR,
                status=FeeStatus.KNOWN,
                currency=f.USDT.key,
                source="test",
                observed_at=f.NOW,
            )

    def test_confirmed_zero_fee_differs_from_unknown(self) -> None:
        """Подтверждённый ноль и неизвестность — разные состояния."""
        zero = f.known_fee(amount="0")
        assert zero.is_known
        assert zero.known_amount == Decimal("0")
        assert not f.unknown_fee().is_known

    def test_fee_included_in_quote_is_not_deducted_again(self) -> None:
        """Защита от двойного учёта (01 §29, 09 §45)."""
        included = f.known_fee(inclusion=CostInclusion.INCLUDED_IN_QUOTE)
        assert not included.is_deductible
        assert f.known_fee(inclusion=CostInclusion.NOT_INCLUDED).is_deductible

    def test_unknown_inclusion_is_not_deductible(self) -> None:
        assert not f.known_fee(inclusion=CostInclusion.UNKNOWN).is_deductible

    def test_freshness(self) -> None:
        fee = f.known_fee().replace(expires_at=f.NOW + timedelta(hours=1))
        assert fee.is_fresh(f.NOW)
        assert not fee.is_fresh(f.NOW + timedelta(hours=2))

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(ValidationError):
            Fee(
                fee_type=FeeType.AGGREGATOR,
                status=FeeStatus.KNOWN,
                amount=Decimal("-1"),
                currency=f.USDT.key,
                source="test",
                observed_at=f.NOW,
            )


class TestFeeSnapshot:
    def test_detects_unknown_components(self) -> None:
        snapshot = FeeSnapshot(
            snapshot_id="s1",
            provider_id=f.ProviderId.ONEINCH,
            network_id=f.POLYGON,
            operation=f.OperationType.BUY,
            fees=(f.known_fee(), f.unknown_fee()),
            version=1,
            created_at=f.NOW,
        )
        assert snapshot.has_unknown
        assert len(snapshot.of_type(FeeType.AGGREGATOR)) == 1


class TestGas:
    def test_known_gas_is_complete(self) -> None:
        gas = f.known_gas()
        assert gas.is_known
        assert gas.known_cost_native == Decimal("0.03")

    def test_unknown_gas_is_not_zero(self) -> None:
        """UNKNOWN gas не превращается в ноль (09 §16)."""
        gas = f.unknown_gas()
        assert not gas.is_known
        assert gas.cost_native is None
        with pytest.raises(ValueError, match="must not be treated as zero"):
            _ = gas.known_cost_native

    def test_unknown_gas_cannot_carry_cost(self) -> None:
        with pytest.raises(ValidationError, match="not zero"):
            Gas(
                network_id=f.POLYGON,
                status=FeeStatus.UNKNOWN,
                cost_native=Decimal("0"),
                observed_at=f.NOW,
                source="test",
            )

    def test_known_gas_requires_all_components(self) -> None:
        with pytest.raises(ValidationError, match="missing"):
            Gas(
                network_id=f.POLYGON,
                status=FeeStatus.KNOWN,
                gas_units=100,
                observed_at=f.NOW,
                source="test",
            )

    def test_rejects_gas_price_from_other_network(self) -> None:
        with pytest.raises(ValidationError, match="different network"):
            f.known_gas().replace(
                gas_price=GasPrice(
                    network_id="ethereum",
                    wei_per_gas=1,
                    source="test",
                    observed_at=f.NOW,
                ).model_dump()
            )


class TestGasPrice:
    def test_eip1559_components_must_sum_to_total(self) -> None:
        with pytest.raises(ValidationError, match="base_fee_wei \\+ priority_fee_wei"):
            GasPrice(
                network_id=f.POLYGON,
                wei_per_gas=100,
                base_fee_wei=60,
                priority_fee_wei=30,
                source="rpc",
                observed_at=f.NOW,
            )

    def test_accepts_consistent_eip1559(self) -> None:
        price = GasPrice(
            network_id=f.POLYGON,
            wei_per_gas=90,
            base_fee_wei=60,
            priority_fee_wei=30,
            source="rpc",
            observed_at=f.NOW,
        )
        assert price.wei_per_gas == 90

    def test_legacy_price_without_components_is_allowed(self) -> None:
        price = GasPrice(network_id=f.POLYGON, wei_per_gas=50, source="rpc", observed_at=f.NOW)
        assert price.base_fee_wei is None


class TestConversionRate:
    def test_converts(self) -> None:
        rate = ConversionRate(
            from_token=f.WMATIC.key,
            to_token=f.USDT.key,
            rate=Decimal("0.42"),
            source="test",
            observed_at=f.NOW,
        )
        assert rate.convert(Decimal("10")) == Decimal("4.20")

    def test_direction_matters(self) -> None:
        """ETH -> USDT не равно USDT -> ETH (09 §38)."""
        rate = ConversionRate(
            from_token=f.WMATIC.key,
            to_token=f.USDT.key,
            rate=Decimal("0.5"),
            source="test",
            observed_at=f.NOW,
        )
        inverse = rate.inverted()
        assert inverse.from_token == f.USDT.key
        assert inverse.rate == Decimal("2")

    def test_rejects_same_token(self) -> None:
        with pytest.raises(ValidationError, match="two different tokens"):
            ConversionRate(
                from_token=f.USDT.key,
                to_token=f.USDT.key,
                rate=Decimal("1"),
                source="test",
                observed_at=f.NOW,
            )

    def test_stale_rate_is_detectable(self) -> None:
        rate = ConversionRate(
            from_token=f.WMATIC.key,
            to_token=f.USDT.key,
            rate=Decimal("0.5"),
            source="test",
            observed_at=f.NOW,
            expires_at=f.NOW + timedelta(minutes=5),
        )
        assert rate.is_fresh(f.NOW)
        assert not rate.is_fresh(f.NOW + timedelta(minutes=6))


class TestThresholdOutcome:
    def test_unknown_cost_blocks_pass(self) -> None:
        """Неизвестный расход не позволяет пройти порог (09 §27)."""
        with pytest.raises(ValidationError, match="unknown"):
            ThresholdOutcome(
                metric=ThresholdMetric.NET_ROI,
                threshold=Decimal("1"),
                actual=Decimal("1.2"),
                passed=True,
                blocked_by_unknown_cost=True,
            )

    def test_cannot_pass_without_actual_value(self) -> None:
        with pytest.raises(ValidationError, match="actual metric"):
            ThresholdOutcome(
                metric=ThresholdMetric.NET_ROI,
                threshold=Decimal("1"),
                actual=None,
                passed=True,
            )

    def test_boundary_value_may_pass(self) -> None:
        """net_roi = threshold проходит порог (09 §26)."""
        outcome = ThresholdOutcome(
            metric=ThresholdMetric.NET_ROI,
            threshold=Decimal("1.00"),
            actual=Decimal("1.00"),
            passed=True,
        )
        assert outcome.passed


class TestCostBreakdown:
    def test_total_costs_subtracts_rebates(self) -> None:
        """Rebate уменьшает итоговую стоимость (09 §15)."""
        breakdown = CostBreakdown(
            total_fees=Decimal("0.30"),
            gas_cost=Decimal("0.30"),
            other_costs=Decimal("0"),
            rebates=Decimal("0.05"),
        )
        assert breakdown.total_costs == Decimal("0.55")


class TestProfitResult:
    def test_complete_requires_all_components(self) -> None:
        with pytest.raises(ValidationError, match="missing"):
            f.profit_result().replace(net_profit=None)

    def test_complete_forbids_unknown_components(self) -> None:
        result = f.profit_result()
        assert result.costs is not None
        with pytest.raises(ValidationError, match="unknown cost components"):
            result.replace(costs={**result.costs.model_dump(), "unknown_components": ("gas",)})

    def test_partial_is_not_profitable(self) -> None:
        """PARTIAL не является подтверждением прибыльности (09 §19)."""
        assert not f.profit_result(status=CalculationStatus.PARTIAL).is_profitable

    def test_failed_threshold_is_not_profitable(self) -> None:
        assert not f.profit_result(net_roi="0.50", passed=False).is_profitable

    def test_profitable_requires_complete_and_passed(self) -> None:
        assert f.profit_result().is_profitable

    def test_formula_version_is_recorded(self) -> None:
        """Историю нельзя интерпретировать новой формулой (09 §68)."""
        assert f.profit_result().formula_version == PROFIT_FORMULA_VERSION


class TestProfitCalculationInput:
    def _input(self, **overrides: object) -> ProfitCalculationInput:
        base = {
            "input_amount": f.USDT.amount_from_base_units(100_000_000),
            "input_token": f.USDT.key,
            "buy_output": f.AAVE.amount_from_base_units(5_000_000_000_000_000_000),
            "intermediate_token": f.AAVE.key,
            "sell_output": f.USDT.amount_from_base_units(101_500_000),
            "output_token": f.USDT.key,
            "threshold": Decimal("1.00"),
        }
        base.update(overrides)
        return ProfitCalculationInput(**base)  # type: ignore[arg-type]

    def test_accepts_valid_input(self) -> None:
        assert self._input().threshold == Decimal("1.00")

    def test_rejects_zero_input_amount(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            self._input(input_amount=f.USDT.amount_from_base_units(0))

    def test_rejects_cross_network(self) -> None:
        foreign = f.TokenKey(network_id="ethereum", address=f.USDT.address)
        with pytest.raises(ValidationError, match="cross-network"):
            self._input(output_token=foreign)

    def test_rejects_float_threshold(self) -> None:
        with pytest.raises(ValidationError):
            self._input(threshold=1.0)
