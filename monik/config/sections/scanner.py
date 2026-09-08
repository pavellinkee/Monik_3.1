"""Конфигурация Level 1 и Level 2."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.domain.enums.scheduler import OverlapPolicy
from monik.domain.value_objects.identity import NetworkId, TokenAddress
from monik.domain.value_objects.numeric import PositiveDecimal

__all__ = ["Level1Config", "Level2Config", "ScannerConfig"]


class Level1Config(ConfigSection):
    """Параметры Level 1 (``17_CONFIGURATION.md`` §32-34).

    Интервал сканирования по умолчанию — 5 минут
    (``02_LEVEL1_SCANNER.md`` §64). При наложении запусков применяется
    ``SKIP`` (``02_LEVEL1_SCANNER.md`` §65).
    """

    enabled: bool = True
    interval_seconds: int = Field(default=300, ge=1, le=86_400)
    overlap_policy: OverlapPolicy = OverlapPolicy.SKIP
    scan_timeout_seconds: int = Field(default=240, ge=1, le=86_400)
    top_tokens: int = Field(default=30, ge=1, le=500)
    max_opportunities_per_scan: int = Field(default=50, ge=1, le=1000)
    max_concurrent_requests: int = Field(default=8, ge=1, le=256)
    quote_max_age_seconds: int = Field(default=30, ge=1, le=3600)
    opportunity_ttl_seconds: int = Field(default=120, ge=1, le=3600)
    deduplication_window_seconds: int = Field(default=300, ge=0, le=86_400)
    allow_unknown_capability: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.scan_timeout_seconds > self.interval_seconds:
            raise ValueError(
                "scan_timeout_seconds must not exceed interval_seconds, "
                "otherwise scans would overlap by design"
            )
        return self


class Level2Config(ConfigSection):
    """Параметры Level 2 (``17_CONFIGURATION.md`` §35).

    ``max_parallel`` по умолчанию 20 (``CLAUDE.md`` §18,
    ``04_SCHEDULER.md`` §21) и никогда не превышается.
    """

    enabled: bool = True
    max_parallel: int = Field(default=20, ge=1, le=200)
    queue_capacity: int = Field(default=200, ge=1, le=10_000)
    job_ttl_seconds: int = Field(default=120, ge=1, le=3600)
    confirmation_timeout_seconds: int = Field(default=60, ge=1, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=10)
    quote_max_age_seconds: int = Field(default=15, ge=1, le=3600)
    require_route_confirmation: bool = True

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Проверка маршрута обязательна.

        Без подтверждения маршрута Level 2 подтверждал бы возможность на
        маршруте, отличном от найденного Level 1
        (``11_LEVEL_2_SCANNER.md`` §18, §24).
        """
        if not self.require_route_confirmation:
            raise ValueError(
                "require_route_confirmation cannot be disabled: Level 2 must verify the "
                "exact route fixed by Level 1"
            )
        if self.confirmation_timeout_seconds > self.job_ttl_seconds:
            raise ValueError("confirmation_timeout_seconds must not exceed job_ttl_seconds")
        return self


class ScannerConfig(ConfigSection):
    """Общие параметры сканирования (``17_CONFIGURATION.md`` §21-22).

    Суммы задаются только конфигурацией: hard-code сумм в коде запрещён
    (``01_PROJECT_REQUIREMENTS.md`` §22).
    """

    base_network: NetworkId
    base_token_address: TokenAddress
    amounts: tuple[PositiveDecimal, ...] = Field(min_length=1)
    level1: Level1Config = Level1Config()
    level2: Level2Config = Level2Config()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if len(set(self.amounts)) != len(self.amounts):
            raise ValueError("scanner amounts must be unique")
        if any(amount <= Decimal(0) for amount in self.amounts):
            raise ValueError("scanner amounts must be positive")
        return self
