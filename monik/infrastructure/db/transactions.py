"""Абстракция транзакций для repository layer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from monik.infrastructure.db.connection import Database, Transaction

__all__ = ["TransactionManager"]


class TransactionManager:
    """Границы атомарных операций (``38_INTERFACES.md`` §76-78).

    Критические многошаговые записи выполняются внутри одной транзакции —
    например создание Opportunity вместе с её Level 2 Job
    (``CLAUDE.md`` §29).

    Транзакция никогда не удерживается во время внешнего запроса к
    провайдеру или Telegram (``38_INTERFACES.md`` §78).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[Transaction]:
        """Открыть транзакцию; commit при успехе, rollback при исключении."""
        async with self._database.transaction() as connection:
            yield connection
