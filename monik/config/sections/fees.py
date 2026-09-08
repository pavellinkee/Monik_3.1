"""Конфигурация Fee System, gas и цен."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.base import DomainEnum

__all__ = ["FeeConfig", "GasConfig", "GasSource", "PriceConfig", "PriceSource"]


class GasSource(DomainEnum):
    """Источник цены газа (решение D-4).

    Бизнес-логика не привязана к конкретному источнику: реализация
    выбирается конфигурацией.
    """

    RPC = "rpc"
    ADAPTER_ESTIMATE = "adapter_estimate"
    STATIC = "static"


class PriceSource(DomainEnum):
    """Источник курса токена в базовой валюте расчёта (решение D-4)."""

    AGGREGATOR_QUOTE = "aggregator_quote"
    HTTP = "http"
    STATIC = "static"


class FeeConfig(ConfigSection):
    """Параметры Fee System (``17_CONFIGURATION.md`` §38-39).

    Поведение при UNKNOWN обязательной комиссии зафиксировано архитектурой:
    неизвестная комиссия никогда не считается нулевой
    (``07_FEE_SYSTEM.md`` §15), поэтому соответствующий флаг не отключается.
    """

    enabled: bool = True
    refresh_on_startup: bool = True
    refresh_interval_days: int = Field(default=1, ge=1, le=365)
    refresh_time: str = Field(default="02:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    freshness_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    treat_unknown_as_zero: bool = False
    batch_enabled: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.treat_unknown_as_zero:
            raise ValueError(
                "treat_unknown_as_zero must remain false: an unknown mandatory fee "
                "is not a zero fee"
            )
        return self


class GasConfig(ConfigSection):
    """Параметры получения gas (``17_CONFIGURATION.md`` §40, решение D-4)."""

    enabled: bool = True
    sources: tuple[GasSource, ...] = (GasSource.ADAPTER_ESTIMATE, GasSource.RPC)
    freshness_seconds: int = Field(default=60, ge=1, le=3600)
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    treat_unknown_as_zero: bool = False
    #: Явно заданная цена газа в wei по сетям. Используется только при
    #: источнике ``STATIC``: это явно настроенный fallback, а не
    #: production-источник данных.
    static_wei_per_gas: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.treat_unknown_as_zero:
            raise ValueError("treat_unknown_as_zero must remain false: unknown gas is not zero gas")
        if not self.sources:
            raise ValueError("at least one gas source must be configured")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("gas sources must be unique")
        if GasSource.STATIC in self.sources and not self.static_wei_per_gas:
            raise ValueError("static gas source requires static_wei_per_gas")
        if any(value <= 0 for value in self.static_wei_per_gas.values()):
            raise ValueError("static gas price must be positive")
        return self


class PriceConfig(ConfigSection):
    """Параметры конверсии native token в валюту расчёта (решение D-4)."""

    enabled: bool = True
    sources: tuple[PriceSource, ...] = (PriceSource.AGGREGATOR_QUOTE,)
    freshness_seconds: int = Field(default=300, ge=1, le=86_400)
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    http_endpoint: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.sources:
            raise ValueError("at least one price source must be configured")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("price sources must be unique")
        if PriceSource.HTTP in self.sources and not self.http_endpoint:
            raise ValueError("http price source requires http_endpoint")
        if self.http_endpoint is not None and not self.http_endpoint.startswith("https://"):
            raise ValueError("http_endpoint must use https")
        return self
