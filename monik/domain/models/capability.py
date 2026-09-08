"""Capability — подтверждённая поддержка операции провайдером."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["Capability", "CapabilityKey"]


class CapabilityKey(DomainModel):
    """Identity capability (``08_CAPABILITY_REGISTRY.md`` §14).

    Лишние параметры в ключ не добавляются (``08_CAPABILITY_REGISTRY.md`` §15):
    чрезмерная детализация приводит к бесконечному числу проверок.
    """

    provider_id: ProviderId
    network_id: NetworkId
    operation: CapabilityOperation
    token: TokenKey | None = None

    def __str__(self) -> str:
        token = str(self.token) if self.token else "*"
        return f"{self.provider_id.value}/{self.network_id}/{self.operation.value}/{token}"


class Capability(DomainModel):
    """Состояние поддержки конкретной операции (``36_DATA_MODELS.md`` §59).

    ``UNKNOWN`` не эквивалентен ``SUPPORTED`` (``36_DATA_MODELS.md`` §61).
    Просроченная capability не считается актуальной автоматически
    (``30_DATABASE_SCHEMA.md`` §51).
    """

    key: CapabilityKey
    status: CapabilityStatus
    checked_at: UtcDatetime
    expires_at: UtcDatetime | None = None
    source: str = Field(min_length=1, max_length=128)
    consecutive_failures: int = Field(default=0, ge=0)
    detail: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.checked_at:
            raise ValueError("capability expires_at must be after checked_at")
        return self

    def is_fresh(self, now: UtcDatetime) -> bool:
        """Актуальна ли информация о поддержке."""
        return self.expires_at is None or now < self.expires_at

    def allows_request(self, now: UtcDatetime, allow_unknown: bool) -> bool:
        """Можно ли отправлять запрос для этой комбинации.

        Явно неподдерживаемые комбинации не запрашиваются
        (``02_LEVEL1_SCANNER.md`` §76). ``UNKNOWN`` может проверяться в runtime,
        если это разрешено policy (``10_LEVEL_1_SCANNER.md`` §16) — решение
        передаётся параметром ``allow_unknown``, а не принимается моделью.
        """
        if self.status is CapabilityStatus.UNSUPPORTED:
            return False
        if self.status is CapabilityStatus.SUPPORTED:
            return self.is_fresh(now) or allow_unknown
        return allow_unknown
