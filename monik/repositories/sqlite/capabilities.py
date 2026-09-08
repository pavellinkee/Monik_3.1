"""Хранилище capability."""

from __future__ import annotations

import aiosqlite

from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.capability import Capability, CapabilityKey
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId, TokenAddress
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import from_timestamp, to_timestamp
from monik.repositories.sqlite.mapping import column, optional_column

__all__ = ["SqliteCapabilityRepository"]

_COLUMNS = (
    "capability_key, provider_id, network_id, operation, token, status, checked_at, "
    "expires_at, source, consecutive_failures, detail"
)


class SqliteCapabilityRepository:
    """Persistence состояния capability (``38_INTERFACES.md`` §74).

    Сохранённая capability не считается актуальной автоматически: свежесть
    определяется отдельно (``30_DATABASE_SCHEMA.md`` §51).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(self, capability: Capability) -> None:
        """Сохранить или обновить состояние capability."""
        key = capability.key
        await self._database.execute(
            f"INSERT INTO capabilities ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(capability_key) DO UPDATE SET status = excluded.status, "
            "checked_at = excluded.checked_at, expires_at = excluded.expires_at, "
            "source = excluded.source, consecutive_failures = excluded.consecutive_failures, "
            "detail = excluded.detail",
            (
                str(key),
                key.provider_id.value,
                str(key.network_id),
                key.operation.value,
                str(key.token) if key.token else None,
                capability.status.value,
                to_timestamp(capability.checked_at),
                to_timestamp(capability.expires_at) if capability.expires_at else None,
                capability.source,
                capability.consecutive_failures,
                capability.detail,
            ),
        )

    async def get(self, key: CapabilityKey) -> Capability | None:
        """Найти capability по ключу."""
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM capabilities WHERE capability_key = ?", (str(key),)
        )
        return self._to_domain(row) if row else None

    async def list_for_provider(self, provider_id: ProviderId) -> tuple[Capability, ...]:
        """Все известные capability провайдера."""
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM capabilities WHERE provider_id = ? ORDER BY capability_key",
            (provider_id.value,),
        )
        return tuple(self._to_domain(row) for row in rows)

    async def list_all(self) -> tuple[Capability, ...]:
        """Все сохранённые capability."""
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM capabilities ORDER BY capability_key"
        )
        return tuple(self._to_domain(row) for row in rows)

    @staticmethod
    def _to_domain(row: aiosqlite.Row) -> Capability:
        token = optional_column(row, "token")
        expires_at = optional_column(row, "expires_at")
        network_id = NetworkId(str(column(row, "network_id")))
        parsed_token: TokenKey | None = None
        if token:
            _, _, address = str(token).partition(":")
            parsed_token = TokenKey(network_id=network_id, address=TokenAddress(address))
        return Capability(
            key=CapabilityKey(
                provider_id=ProviderId(str(column(row, "provider_id"))),
                network_id=network_id,
                operation=CapabilityOperation(str(column(row, "operation"))),
                token=parsed_token,
            ),
            status=CapabilityStatus(str(column(row, "status"))),
            checked_at=from_timestamp(str(column(row, "checked_at"))),
            expires_at=from_timestamp(str(expires_at)) if expires_at else None,
            source=str(column(row, "source")),
            consecutive_failures=int(column(row, "consecutive_failures")),
            detail=optional_column(row, "detail"),
        )
