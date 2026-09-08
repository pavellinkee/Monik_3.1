"""Scan — один цикл работы Level 1."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.lifecycle import ScanStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identifiers import ScanId
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Scan", "ScanScope", "ScanStatistics"]


class ScanScope(DomainModel):
    """Границы одного цикла (``36_DATA_MODELS.md`` §52).

    Scope фиксируется на момент старта: изменение конфигурации применяется
    со следующего цикла (``02_LEVEL1_SCANNER.md`` §69).
    """

    networks: tuple[NetworkId, ...] = Field(min_length=1)
    providers: tuple[ProviderId, ...] = Field(min_length=1)
    tokens: tuple[TokenKey, ...] = Field(min_length=1)
    raw_amounts: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if any(amount <= 0 for amount in self.raw_amounts):
            raise ValueError("scan amounts must be positive")
        return self


class ScanStatistics(DomainModel):
    """Счётчики цикла (``36_DATA_MODELS.md`` §53).

    Полная история quotes не сохраняется (``30_DATABASE_SCHEMA.md`` §44) —
    хранится только агрегированная статистика.
    """

    quote_requests: int = Field(default=0, ge=0)
    successful_quotes: int = Field(default=0, ge=0)
    failed_quotes: int = Field(default=0, ge=0)
    skipped_combinations: int = Field(default=0, ge=0)
    deduplicated_requests: int = Field(default=0, ge=0)
    opportunities_created: int = Field(default=0, ge=0)
    duplicate_opportunities: int = Field(default=0, ge=0)


class Scan(DomainModel):
    """Один цикл Level 1 (``36_DATA_MODELS.md`` §51)."""

    scan_id: ScanId
    status: ScanStatus
    scope: ScanScope
    statistics: ScanStatistics = ScanStatistics()
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("scan finished_at must not precede started_at")
        if self.status is ScanStatus.RUNNING and self.finished_at is not None:
            raise ValueError("running scan must not have finished_at")
        if self.status is not ScanStatus.RUNNING and self.finished_at is None:
            raise ValueError(f"scan in status {self.status.value} must have finished_at")
        return self
