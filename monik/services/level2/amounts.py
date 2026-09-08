"""Проверка одной суммы Opportunity.

Каждая сумма проверяется на **том же** маршруте (``11_LEVEL_2_SCANNER.md``
§7), но получает собственный финансовый результат (§8). Результат одной
суммы никогда не переносится на другую (§59).

Порядок обязателен: сначала BUY по зафиксированному маршруту, затем SELL —
на **текущем** BUY output, а не на значении Level 1 (§16-17).
"""

from __future__ import annotations

from monik.domain.enums.calculation import CalculationStatus
from monik.domain.enums.lifecycle import AmountVerificationStatus
from monik.domain.models.job import AmountVerificationResult
from monik.domain.models.opportunity import Opportunity, OpportunityAmount
from monik.services.level2.financials import Level2Financials
from monik.services.level2.routes import RouteCheck, RouteVerifier
from monik.services.observability.logging import get_logger, log_fields
from monik.services.registries.tokens import TokenRegistry

__all__ = ["AmountVerifier"]

_LOGGER = get_logger("services.level2.amounts")


class AmountVerifier:
    """Проверяет одну сумму и возвращает её результат."""

    def __init__(
        self,
        routes: RouteVerifier,
        financials: Level2Financials,
        tokens: TokenRegistry,
    ) -> None:
        self._routes = routes
        self._financials = financials
        self._tokens = tokens

    async def verify(
        self, opportunity: Opportunity, amount: OpportunityAmount
    ) -> AmountVerificationResult:
        """Проверить сумму по зафиксированному маршруту."""
        snapshot = opportunity.routes
        input_token = self._tokens.require(snapshot.input_token)
        intermediate_token = self._tokens.require(snapshot.intermediate_token)
        output_token = self._tokens.require(snapshot.output_token)

        buy = await self._routes.verify(
            snapshot.buy_route,
            input_token=input_token,
            output_token=intermediate_token,
            input_amount=amount.input_amount,
        )
        if not buy.is_reproduced or buy.quote is None:
            return _route_failure(amount, buy, leg="buy")

        current_buy_output = buy.quote.output_amount
        sell = await self._routes.verify(
            snapshot.sell_route,
            input_token=intermediate_token,
            output_token=output_token,
            # SELL проверяется именно на текущем BUY output (§16).
            input_amount=current_buy_output,
        )
        if not sell.is_reproduced or sell.quote is None:
            return _route_failure(amount, sell, leg="sell")

        financials = await self._financials.evaluate(buy.quote, sell.quote)
        status = _status_for(financials.result.status, profitable=financials.result.is_profitable)
        _LOGGER.info(
            "amount verified",
            extra=log_fields(
                amount=str(amount.input_amount),
                status=status.value,
                calculation=financials.result.status.value,
            ),
        )
        return AmountVerificationResult(
            input_amount=amount.input_amount,
            status=status,
            buy_quote=buy.quote,
            sell_quote=sell.quote,
            current_buy_output=current_buy_output,
            current_sell_output=sell.quote.output_amount,
            fee_snapshots=financials.fee_snapshots,
            gas=financials.gas,
            profit_result=financials.result,
            rejection_reason=_rejection_reason(status, financials.result.status),
        )


def _status_for(calculation: CalculationStatus, *, profitable: bool) -> AmountVerificationStatus:
    """Статус суммы по результату расчёта.

    ``PARTIAL``/``UNKNOWN`` не считаются убыточностью: неизвестные данные —
    отдельная причина (§52). ``INVALID`` — сбой расчёта, а не отсутствие
    прибыли.
    """
    if calculation is CalculationStatus.COMPLETE:
        return (
            AmountVerificationStatus.VERIFIED_PROFITABLE
            if profitable
            else AmountVerificationStatus.VERIFIED_UNPROFITABLE
        )
    if calculation is CalculationStatus.INVALID:
        return AmountVerificationStatus.FAILED
    return AmountVerificationStatus.UNKNOWN


def _rejection_reason(
    status: AmountVerificationStatus, calculation: CalculationStatus
) -> str | None:
    """Человекочитаемая причина отрицательного результата (§67)."""
    if status is AmountVerificationStatus.VERIFIED_PROFITABLE:
        return None
    if status is AmountVerificationStatus.VERIFIED_UNPROFITABLE:
        return "net result is below the profitability threshold"
    return f"calculation is {calculation.value}: a required value is unknown"


def _route_failure(
    amount: OpportunityAmount,
    check: RouteCheck,
    *,
    leg: str,
) -> AmountVerificationResult:
    """Результат суммы, для которой маршрут не подтверждён.

    Невозможность воспроизвести маршрут не означает убыточность (§51):
    альтернативный маршрут не подбирается.
    """
    detail = check.detail or check.outcome.value
    return AmountVerificationResult(
        input_amount=amount.input_amount,
        status=AmountVerificationStatus.ROUTE_UNAVAILABLE,
        rejection_reason=f"{leg} route not confirmed: {detail}"[:256],
    )
