"""Комиссии и их снимки."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.fingerprints import compute_fingerprint
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.numeric import NonNegativeDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Fee", "FeeKey", "FeeSnapshot"]


class FeeKey(DomainModel):
    """Детерминированный ключ комиссии (``07_FEE_SYSTEM.md`` §45).

    Ключ не должен быть чрезмерно обобщённым (``07_FEE_SYSTEM.md`` §46):
    комиссия, зависящая от маршрута или токена, обязана включать
    соответствующий контекст, иначе значения разных контекстов смешаются.
    """

    provider_id: ProviderId
    network_id: NetworkId
    operation: OperationType
    fee_type: FeeType
    token: TokenKey | None = None
    route_fingerprint: str | None = None

    def __str__(self) -> str:
        return compute_fingerprint(
            {
                "provider_id": self.provider_id.value,
                "network_id": str(self.network_id),
                "operation": self.operation.value,
                "fee_type": self.fee_type.value,
                "token": str(self.token) if self.token else None,
                "route_fingerprint": self.route_fingerprint,
            }
        )


class Fee(DomainModel):
    """Один компонент стоимости (``36_DATA_MODELS.md`` §24).

    ``UNKNOWN`` никогда не эквивалентен нулю (``CLAUDE.md`` §23,
    ``07_FEE_SYSTEM.md`` §15): у такой комиссии ``amount`` отсутствует,
    а не равен нулю. Подтверждённое отсутствие комиссии выражается
    статусом ``KNOWN`` с ``amount = 0``.

    ``inclusion`` защищает от двойного учёта (``09_PROFIT_CALCULATOR.md`` §45).
    """

    fee_type: FeeType
    status: FeeStatus
    amount: NonNegativeDecimal | None = None
    currency: TokenKey | None = None
    inclusion: CostInclusion = CostInclusion.UNKNOWN
    source: str = Field(min_length=1, max_length=128)
    observed_at: UtcDatetime
    expires_at: UtcDatetime | None = None
    description: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _validate_status(self) -> Self:
        """Известная комиссия обязана иметь сумму и валюту, неизвестная — нет."""
        if self.status is FeeStatus.KNOWN:
            if self.amount is None:
                raise ValueError("fee with status KNOWN must carry an amount")
            if self.currency is None:
                raise ValueError("fee with status KNOWN must carry a currency")
        elif self.amount is not None:
            raise ValueError(
                f"fee with status {self.status.value} must not carry an amount; "
                "unknown or unsupported fee is not zero"
            )
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("fee expires_at must be after observed_at")
        return self

    @property
    def is_known(self) -> bool:
        """Известна ли комиссия достоверно."""
        return self.status is FeeStatus.KNOWN

    @property
    def is_deductible(self) -> bool:
        """Нужно ли вычитать комиссию отдельно.

        Комиссия, уже включённая провайдером в output amount, повторно
        не вычитается (``01_PROJECT_REQUIREMENTS.md`` §29).
        """
        return self.is_known and self.inclusion is CostInclusion.NOT_INCLUDED

    @property
    def known_amount(self) -> Decimal:
        """Сумма известной комиссии.

        Обращение к сумме неизвестной комиссии — ошибка: подставлять ноль
        запрещено (``CLAUDE.md`` §12).
        """
        if self.amount is None:
            raise ValueError(f"fee {self.fee_type.value} has no known amount")
        return self.amount

    def is_fresh(self, now: UtcDatetime) -> bool:
        """Актуальна ли комиссия на момент ``now``."""
        if self.status is FeeStatus.EXPIRED:
            return False
        return self.expires_at is None or now < self.expires_at


class FeeSnapshot(DomainModel):
    """Согласованный набор комиссий одного контекста (``07_FEE_SYSTEM.md`` §54).

    Снимок версионируется, чтобы исторический результат можно было
    интерпретировать через ту же версию правил (``07_FEE_SYSTEM.md`` §27).
    """

    snapshot_id: str = Field(min_length=1, max_length=64)
    provider_id: ProviderId
    network_id: NetworkId
    operation: OperationType
    fees: tuple[Fee, ...]
    version: int = Field(ge=1)
    created_at: UtcDatetime

    @property
    def has_unknown(self) -> bool:
        """Есть ли в снимке неизвестные обязательные комиссии."""
        return any(not fee.is_known for fee in self.fees)

    def of_type(self, fee_type: FeeType) -> tuple[Fee, ...]:
        """Все компоненты заданного типа."""
        return tuple(fee for fee in self.fees if fee.fee_type is fee_type)
