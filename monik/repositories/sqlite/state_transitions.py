"""Журнал переходов состояний."""

from __future__ import annotations

import uuid

import aiosqlite

from monik.domain.models.transitions import StateTransitionRecord
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import from_timestamp, to_timestamp
from monik.repositories.sqlite.mapping import column, optional_column

__all__ = ["SqliteStateTransitionRepository", "StateTransitionRecord"]


class SqliteStateTransitionRepository:
    """Persistence журнала переходов."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(self, transition: StateTransitionRecord) -> None:
        """Записать переход."""
        await self._database.execute(
            "INSERT INTO state_transitions (transition_id, entity_type, entity_id, from_state, "
            "to_state, reason, correlation_id, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                transition.entity_type,
                transition.entity_id,
                transition.from_state,
                transition.to_state,
                transition.reason,
                transition.correlation_id,
                to_timestamp(transition.occurred_at),
            ),
        )

    async def history(
        self, entity_type: str, entity_id: str, *, limit: int = 100
    ) -> tuple[StateTransitionRecord, ...]:
        """История переходов сущности в хронологическом порядке."""
        rows = await self._database.fetch_all(
            "SELECT entity_type, entity_id, from_state, to_state, reason, correlation_id, "
            "occurred_at FROM state_transitions WHERE entity_type = ? AND entity_id = ? "
            "ORDER BY occurred_at LIMIT ?",
            (entity_type, entity_id, limit),
        )
        return tuple(self._to_domain(row) for row in rows)

    async def delete_before(self, moment: UtcDatetime) -> int:
        """Удалить устаревшие записи журнала."""
        rows = await self._database.fetch_all(
            "SELECT transition_id FROM state_transitions WHERE occurred_at < ?",
            (to_timestamp(moment),),
        )
        if not rows:
            return 0
        await self._database.execute(
            "DELETE FROM state_transitions WHERE occurred_at < ?", (to_timestamp(moment),)
        )
        return len(rows)

    @staticmethod
    def _to_domain(row: aiosqlite.Row) -> StateTransitionRecord:
        return StateTransitionRecord(
            entity_type=str(column(row, "entity_type")),
            entity_id=str(column(row, "entity_id")),
            from_state=optional_column(row, "from_state"),
            to_state=str(column(row, "to_state")),
            reason=str(column(row, "reason")),
            correlation_id=optional_column(row, "correlation_id"),
            occurred_at=from_timestamp(str(column(row, "occurred_at"))),
        )
