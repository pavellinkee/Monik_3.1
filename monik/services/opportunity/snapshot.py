"""Сборка immutable снимка подтверждения.

Снимок собирается из уже полученных данных: Opportunity, зафиксировавшей
маршрут, и результата Level 2. Никаких пересчётов здесь нет
(``15_NOTIFICATION_SYSTEM.md`` §14) — значения переносятся как есть.
"""

from __future__ import annotations

from monik.domain.models.confirmation import AmountSnapshot, ConfirmationSnapshot
from monik.domain.models.job import AmountVerificationResult, ConfirmationResult
from monik.domain.models.opportunity import Opportunity
from monik.domain.models.profit import PROFIT_FORMULA_VERSION

__all__ = ["build_snapshot"]


def build_snapshot(opportunity: Opportunity, result: ConfirmationResult) -> ConfirmationSnapshot:
    """Собрать снимок подтверждения одной Opportunity."""
    if result.opportunity_id != opportunity.opportunity_id:
        raise ValueError("confirmation result belongs to a different opportunity")
    amounts = tuple(_amount_snapshot(item) for item in result.amount_results)
    return ConfirmationSnapshot(
        opportunity_id=opportunity.opportunity_id,
        v_id=opportunity.v_id,
        k_id=result.k_id,
        revision=result.revision,
        network_id=opportunity.network_id,
        input_token=opportunity.input_token,
        intermediate_token=opportunity.intermediate_token,
        output_token=opportunity.output_token,
        buy_provider_id=opportunity.buy_provider_id,
        sell_provider_id=opportunity.sell_provider_id,
        routes=opportunity.routes,
        amounts=amounts,
        formula_version=_formula_version(result.amount_results),
        detected_at=opportunity.detected_at,
        confirmed_at=result.completed_at,
    )


def _amount_snapshot(result: AmountVerificationResult) -> AmountSnapshot:
    """Снимок одной суммы без пересчёта её результата."""
    profit = result.profit_result
    outcome = profit.threshold_outcome if profit is not None else None
    return AmountSnapshot(
        input_amount=result.input_amount,
        status=result.status,
        confirmation_status=result.confirmation_status,
        buy_output=result.current_buy_output,
        sell_output=result.current_sell_output,
        calculation_status=profit.status if profit is not None else None,
        gross_profit=profit.gross_profit if profit is not None else None,
        gross_roi=profit.gross_roi if profit is not None else None,
        net_profit=profit.net_profit if profit is not None else None,
        net_roi=profit.net_roi if profit is not None else None,
        costs=profit.costs if profit is not None else None,
        gas=result.gas,
        fee_snapshots=result.fee_snapshots,
        threshold=outcome.threshold if outcome is not None else None,
        threshold_metric=outcome.metric if outcome is not None else None,
        threshold_passed=outcome.passed if outcome is not None else False,
        rejection_reason=result.rejection_reason,
    )


def _formula_version(results: tuple[AmountVerificationResult, ...]) -> int:
    """Версия финансовой формулы, использованная при проверке (``09`` §67-68)."""
    versions = {
        result.profit_result.formula_version
        for result in results
        if result.profit_result is not None
    }
    if len(versions) > 1:
        raise ValueError(f"confirmation mixes formula versions: {sorted(versions)}")
    return versions.pop() if versions else PROFIT_FORMULA_VERSION
