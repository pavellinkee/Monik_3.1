"""Сборка финансового входа Level 2 для одной суммы.

Все финансовые расчёты выполняет Profit Calculator
(``11_LEVEL_2_SCANNER.md`` §37): собственных формул прибыли, ROI, комиссий
и газа у Level 2 нет.

Здесь собираются **свежие** данные (§38): исходная сумма, текущий BUY
output, текущий SELL output, применимые комиссии, gas и курсы. Снимок
комиссий сохраняется для аудита подтверждения (§65).
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.config.sections.profitability import ProfitabilityConfig
from monik.domain.models.conversion import ConversionRate
from monik.domain.models.fee import Fee, FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.profit import ProfitCalculationInput, ProfitResult
from monik.domain.models.quote import Quote
from monik.services.calculator.profit import ProfitCalculator
from monik.services.fees.context import FeeContext
from monik.services.level2.ports import FeeSnapshotSource, GasSource, RateSource
from monik.services.registries.networks import NetworkRegistry
from monik.services.registries.tokens import TokenRegistry

__all__ = ["Level2Financials", "VerificationFinancials"]


@dataclass(frozen=True, slots=True)
class VerificationFinancials:
    """Финансовый итог проверки одной суммы вместе со снимками."""

    result: ProfitResult
    fee_snapshots: tuple[FeeSnapshot, ...]
    gas: Gas


class Level2Financials:
    """Готовит вход расчёта и получает результат для одной суммы."""

    def __init__(
        self,
        calculator: ProfitCalculator,
        *,
        fees: FeeSnapshotSource,
        gas: GasSource,
        rates: RateSource,
        tokens: TokenRegistry,
        networks: NetworkRegistry,
        profitability: ProfitabilityConfig,
    ) -> None:
        self._calculator = calculator
        self._fees = fees
        self._gas = gas
        self._rates = rates
        self._tokens = tokens
        self._networks = networks
        self._profitability = profitability

    async def evaluate(self, buy_quote: Quote, sell_quote: Quote) -> VerificationFinancials:
        """Рассчитать прибыльность суммы по свежим котировкам.

        Порог — окончательный (``11_LEVEL_2_SCANNER.md`` §43), в отличие от
        предварительного порога Level 1.
        """
        snapshots = (
            await self._fees.snapshot_for(_fee_context(buy_quote)),
            await self._fees.snapshot_for(_fee_context(sell_quote)),
        )
        fees: tuple[Fee, ...] = tuple(fee for snapshot in snapshots for fee in snapshot.fees)
        gas = await self._gas.estimate(
            buy_quote.network_id,
            gas_units=_total_gas_units(buy_quote, sell_quote),
            source="level2_verification",
        )
        rate = await self._gas_conversion_rate(buy_quote, sell_quote)
        result = self._calculator.calculate(
            ProfitCalculationInput(
                input_amount=buy_quote.input_amount,
                input_token=buy_quote.input_token,
                buy_output=buy_quote.output_amount,
                intermediate_token=buy_quote.output_token,
                sell_output=sell_quote.output_amount,
                output_token=sell_quote.output_token,
                fees=fees,
                gas=gas,
                conversion_rates=() if rate is None else (rate,),
                threshold=self._profitability.final_threshold_percent,
                threshold_metric=self._profitability.threshold_metric,
            )
        )
        return VerificationFinancials(result=result, fee_snapshots=snapshots, gas=gas)

    async def _gas_conversion_rate(
        self, buy_quote: Quote, sell_quote: Quote
    ) -> ConversionRate | None:
        """Курс native token в валюту расчёта.

        Отсутствие курса делает стоимость газа неизвестной, а не нулевой
        (``11_LEVEL_2_SCANNER.md`` §35-36).
        """
        native_key = self._networks.wrapped_native_token(buy_quote.network_id)
        native = self._tokens.get(native_key)
        target = self._tokens.get(sell_quote.output_token)
        if native is None or target is None or native.key == target.key:
            return None
        return await self._rates.rate(native, target)


def _fee_context(quote: Quote) -> FeeContext:
    """Контекст комиссий конкретной ноги проверки."""
    return FeeContext(
        provider_id=quote.provider_id,
        network_id=quote.network_id,
        operation=quote.operation,
        input_token=quote.input_token,
        output_token=quote.output_token,
        input_amount=quote.input_amount,
        route_fingerprint=quote.route.fingerprint,
    )


def _total_gas_units(buy_quote: Quote, sell_quote: Quote) -> int | None:
    """Суммарная оценка газа round-trip; неполные данные дают ``None``."""
    if buy_quote.estimated_gas_units is None or sell_quote.estimated_gas_units is None:
        return None
    return buy_quote.estimated_gas_units + sell_quote.estimated_gas_units
