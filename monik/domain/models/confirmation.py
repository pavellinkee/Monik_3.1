"""Immutable снимок подтверждённой возможности.

Notification System получает готовый снимок и ничего не пересчитывает
(``15_NOTIFICATION_SYSTEM.md`` §14): состав снимка задан §8 того же
документа.

После создания финансовые данные не изменяются обычным workflow
(``35_STATE_MACHINES.md`` §66): модель frozen, поэтому попытка присваивания
приводит к ошибке, а не к молчаливой правке (``35_STATE_MACHINES.md`` §67).
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.calculation import CalculationStatus, ThresholdMetric
from monik.domain.enums.lifecycle import AmountConfirmationStatus, AmountVerificationStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.fee import FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.opportunity import RouteSnapshot
from monik.domain.models.profit import CostBreakdown
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.amounts import Percentage, TokenAmount
from monik.domain.value_objects.identifiers import KId, OpportunityId, VId
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.numeric import SignedDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["AmountSnapshot", "ConfirmationSnapshot"]


class AmountSnapshot(DomainModel):
    """Финансовый снимок одной суммы (``15_NOTIFICATION_SYSTEM.md`` §8, §15).

    Каждая сумма хранит собственный результат: значения одной суммы не
    переносятся на другую (``11_LEVEL_2_SCANNER.md`` §59).
    """

    input_amount: TokenAmount
    status: AmountVerificationStatus
    confirmation_status: AmountConfirmationStatus
    buy_output: TokenAmount | None = None
    sell_output: TokenAmount | None = None
    calculation_status: CalculationStatus | None = None
    gross_profit: SignedDecimal | None = None
    gross_roi: Percentage | None = None
    net_profit: SignedDecimal | None = None
    net_roi: Percentage | None = None
    costs: CostBreakdown | None = None
    gas: Gas | None = None
    fee_snapshots: tuple[FeeSnapshot, ...] = ()
    threshold: SignedDecimal | None = None
    threshold_metric: ThresholdMetric | None = None
    threshold_passed: bool = False
    rejection_reason: str | None = Field(default=None, max_length=256)

    @property
    def is_confirmed(self) -> bool:
        """Подтверждена ли сумма."""
        return self.confirmation_status is AmountConfirmationStatus.CONFIRMED


class ConfirmationSnapshot(DomainModel):
    """Снимок подтверждения Level 2, пригодный для доставки и аудита.

    Содержит всё, что требуется уведомлению и разбору «почему»
    (``11_LEVEL_2_SCANNER.md`` §67), поэтому обработка уведомления не
    выполняет новых внешних запросов (``CLAUDE.md`` §35).
    """

    opportunity_id: OpportunityId
    v_id: VId
    k_id: KId
    revision: int = Field(ge=1)
    network_id: NetworkId
    input_token: TokenKey
    intermediate_token: TokenKey
    output_token: TokenKey
    buy_provider_id: ProviderId
    sell_provider_id: ProviderId
    routes: RouteSnapshot
    amounts: tuple[AmountSnapshot, ...] = Field(min_length=1)
    formula_version: int = Field(ge=1)
    detected_at: UtcDatetime
    confirmed_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Снимок обязан быть согласован с зафиксированным маршрутом."""
        if self.routes.network_id != self.network_id:
            raise ValueError("snapshot routes belong to a different network")
        if self.routes.input_token != self.input_token:
            raise ValueError("snapshot input token does not match the fixed route")
        if self.routes.intermediate_token != self.intermediate_token:
            raise ValueError("snapshot intermediate token does not match the fixed route")
        if self.routes.output_token != self.output_token:
            raise ValueError("snapshot output token does not match the fixed route")
        if self.routes.buy_route.provider_id != self.buy_provider_id:
            raise ValueError("snapshot buy provider does not match the fixed route")
        if self.routes.sell_route.provider_id != self.sell_provider_id:
            raise ValueError("snapshot sell provider does not match the fixed route")
        if self.confirmed_at < self.detected_at:
            raise ValueError("snapshot confirmed_at must not precede detected_at")
        return self

    @property
    def confirmed_amounts(self) -> tuple[AmountSnapshot, ...]:
        """Суммы, подтверждённые Level 2."""
        return tuple(amount for amount in self.amounts if amount.is_confirmed)

    @property
    def has_confirmed_amount(self) -> bool:
        """Есть ли хотя бы одна подтверждённая сумма (``CLAUDE.md`` §26)."""
        return bool(self.confirmed_amounts)
