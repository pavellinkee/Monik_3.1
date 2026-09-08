"""Gas: цена, оценка и стоимость исполнения."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.fees import CostInclusion, FeeStatus
from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.numeric import NonNegativeDecimal
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Gas", "GasPrice"]


class GasPrice(DomainModel):
    """Цена газа в сети (решение D-4).

    Поддерживает и legacy ``gas_price``, и EIP-1559 (``base_fee`` +
    ``priority_fee``). Значения хранятся в wei как целые числа: это raw
    blockchain amounts (``09_PROFIT_CALCULATOR.md`` §4).
    """

    network_id: NetworkId
    wei_per_gas: int = Field(ge=0)
    base_fee_wei: int | None = Field(default=None, ge=0)
    priority_fee_wei: int | None = Field(default=None, ge=0)
    source: str = Field(min_length=1, max_length=128)
    observed_at: UtcDatetime
    expires_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("gas price expires_at must be after observed_at")
        if self.base_fee_wei is not None and self.priority_fee_wei is not None:
            expected = self.base_fee_wei + self.priority_fee_wei
            if self.wei_per_gas != expected:
                raise ValueError(
                    "wei_per_gas must equal base_fee_wei + priority_fee_wei "
                    f"({self.wei_per_gas} != {expected})"
                )
        return self

    def is_fresh(self, now: UtcDatetime) -> bool:
        """Актуальна ли цена газа на момент ``now``."""
        return self.expires_at is None or now < self.expires_at


class Gas(DomainModel):
    """Стоимость исполнения операции (``36_DATA_MODELS.md`` §26).

    ``UNKNOWN`` gas никогда не превращается в ноль
    (``09_PROFIT_CALCULATOR.md`` §16, ``CLAUDE.md`` §12): у неизвестного gas
    отсутствуют ``gas_units``/``cost_native``, а не проставлены нули.

    Стоимость хранится в native token сети; перевод в валюту расчёта
    выполняет ConversionService, а не эта модель
    (``07_FEE_SYSTEM.md`` §52).

    ``inclusion`` защищает от повторного вычитания gas, уже учтённого в
    исходном financial value (``09_PROFIT_CALCULATOR.md`` §46). Значение
    по умолчанию — ``NOT_INCLUDED``: quote агрегатора сообщает output
    amount в токене и gas в него не входит.
    """

    network_id: NetworkId
    status: FeeStatus
    gas_units: int | None = Field(default=None, ge=0)
    gas_price: GasPrice | None = None
    native_token: TokenKey | None = None
    cost_native: NonNegativeDecimal | None = None
    inclusion: CostInclusion = CostInclusion.NOT_INCLUDED
    observed_at: UtcDatetime
    source: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_status(self) -> Self:
        """Известный gas обязан быть полным, неизвестный — пустым."""
        if self.status is FeeStatus.KNOWN:
            missing = [
                name
                for name, value in (
                    ("gas_units", self.gas_units),
                    ("gas_price", self.gas_price),
                    ("native_token", self.native_token),
                    ("cost_native", self.cost_native),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"gas with status KNOWN is missing: {', '.join(missing)}")
        elif self.cost_native is not None:
            raise ValueError(
                f"gas with status {self.status.value} must not carry a cost; "
                "unknown gas is not zero"
            )
        if self.gas_price is not None and self.gas_price.network_id != self.network_id:
            raise ValueError("gas price belongs to a different network")
        return self

    @property
    def is_known(self) -> bool:
        """Известна ли стоимость газа достоверно."""
        return self.status is FeeStatus.KNOWN

    @property
    def known_cost_native(self) -> Decimal:
        """Стоимость газа в native token.

        Обращение при неизвестном gas — ошибка: подставлять ноль запрещено.
        """
        if self.cost_native is None:
            raise ValueError("gas cost is unknown and must not be treated as zero")
        return self.cost_native
