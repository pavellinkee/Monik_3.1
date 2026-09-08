"""Normalized quote — снимок состояния внешнего рынка."""

from __future__ import annotations

from datetime import timedelta
from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.quotes import QuoteStatus
from monik.domain.models.base import DomainModel
from monik.domain.models.route import Route
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.amounts import Percentage, TokenAmount
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.numeric import NonNegativeDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Quote"]


class Quote(DomainModel):
    """Нормализованная котировка (``36_DATA_MODELS.md`` §19).

    Quote — снимок внешнего состояния, а не гарантия будущего исполнения
    (``36_DATA_MODELS.md`` §20). Raw ответ провайдера canonical quote не является
    (``36_DATA_MODELS.md`` §22): нормализацию выполняет Adapter.

    Свежесть определяется policy, а не только наличием timestamp
    (``36_DATA_MODELS.md`` §21), поэтому :meth:`is_fresh` принимает
    максимально допустимый возраст явным параметром.
    """

    provider_id: ProviderId
    network_id: NetworkId
    operation: OperationType
    input_token: TokenKey
    output_token: TokenKey
    input_amount: TokenAmount
    output_amount: TokenAmount
    route: Route
    created_at: UtcDatetime
    request_id: RequestId
    status: QuoteStatus = QuoteStatus.VALID
    expires_at: UtcDatetime | None = None
    estimated_gas_units: int | None = Field(default=None, ge=0)
    price_impact: Percentage | None = None
    slippage_bps: int | None = Field(default=None, ge=0, le=10_000)
    provider_metadata: tuple[tuple[str, str], ...] = ()
    raw_output_amount_includes_fees: bool | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        """Quote обязан быть внутренне согласован (``36_DATA_MODELS.md`` §86-87)."""
        if self.input_token.network_id != self.network_id:
            raise ValueError("quote input token belongs to a different network")
        if self.output_token.network_id != self.network_id:
            raise ValueError("quote output token belongs to a different network")
        if self.route.network_id != self.network_id:
            raise ValueError("quote route belongs to a different network")
        if self.route.provider_id != self.provider_id:
            raise ValueError("quote route provider does not match quote provider")
        if self.route.operation != self.operation:
            raise ValueError("quote route operation does not match quote operation")
        if self.route.input_token != self.input_token:
            raise ValueError("quote route input token does not match quote input token")
        if self.route.output_token != self.output_token:
            raise ValueError("quote route output token does not match quote output token")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("quote expires_at must be after created_at")
        return self

    @property
    def has_usable_output(self) -> bool:
        """Есть ли ненулевой output.

        Нулевой output не является валидной прибыльной возможностью
        (``02_LEVEL1_SCANNER.md`` §25).
        """
        return not self.output_amount.is_zero()

    def age(self, now: UtcDatetime) -> timedelta:
        """Возраст котировки на момент ``now``."""
        return now - self.created_at

    def is_fresh(self, now: UtcDatetime, max_age: timedelta) -> bool:
        """Свежа ли котировка согласно переданной policy.

        Явно истёкший ``expires_at`` делает котировку несвежей независимо
        от ``max_age``.
        """
        if self.status is not QuoteStatus.VALID:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return self.age(now) <= max_age

    @property
    def implied_rate(self) -> NonNegativeDecimal:
        """Курс ``output / input`` в человекочитаемых единицах.

        Используется только для диагностики и ранжирования; финансовые решения
        принимает Profit Calculator.
        """
        input_value = self.input_amount.as_decimal
        if input_value == 0:
            raise ValueError("cannot compute implied rate for zero input amount")
        return self.output_amount.as_decimal / input_value
