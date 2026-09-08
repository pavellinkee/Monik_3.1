"""Переход состояния как наблюдаемый факт.

Каждый критический переход должен быть наблюдаем
(``35_STATE_MACHINES.md`` §118): сущность, предыдущее и новое состояние,
момент, машиночитаемая причина и correlation id.

Запись описывает факт и не изменяет саму сущность.
"""

from __future__ import annotations

from pydantic import Field

from monik.domain.models.base import DomainModel
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["StateTransitionRecord"]


class StateTransitionRecord(DomainModel):
    """Зафиксированный переход состояния."""

    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
    from_state: str | None = Field(default=None, max_length=64)
    to_state: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=256)
    occurred_at: UtcDatetime
    correlation_id: str | None = Field(default=None, max_length=64)
