"""Монотонные последовательности в SQLite."""

from __future__ import annotations

from monik.domain.errors import DatabaseError
from monik.infrastructure.db.connection import Database

__all__ = [
    "JOB_SEQUENCE",
    "NOTIFICATION_SEQUENCE",
    "OPPORTUNITY_SEQUENCE",
    "SqliteIdSequenceRepository",
]

#: Имена последовательностей. Пространства ``#V`` и ``#K`` независимы
#: (``CLAUDE.md`` §20), поэтому счётчики раздельные.
OPPORTUNITY_SEQUENCE = "opportunity"
JOB_SEQUENCE = "level2_job"
NOTIFICATION_SEQUENCE = "notification"


class SqliteIdSequenceRepository:
    """Выдаёт монотонные номера, сохраняя состояние в базе.

    Значение увеличивается атомарно внутри транзакции, поэтому после
    рестарта нумерация продолжается, а не начинается заново.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def next_value(self, name: str) -> int:
        """Выдать следующий номер последовательности."""
        async with self._database.transaction() as tx:
            await tx.execute(
                "INSERT INTO id_sequences (name, next_value) VALUES (?, 1) "
                "ON CONFLICT(name) DO UPDATE SET next_value = next_value + 1",
                (name,),
            )
            row = await tx.fetch_one("SELECT next_value FROM id_sequences WHERE name = ?", (name,))
        if row is None:  # pragma: no cover - строка гарантированно существует
            raise DatabaseError(f"sequence {name} disappeared", code="sequence_missing")
        return int(row["next_value"])

    async def current_value(self, name: str) -> int:
        """Текущее значение последовательности."""
        row = await self._database.fetch_one(
            "SELECT next_value FROM id_sequences WHERE name = ?", (name,)
        )
        return int(row["next_value"]) if row else 0
