"""Хранилище снимков комиссий и gas."""

from __future__ import annotations

import uuid

import aiosqlite

from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.fee import Fee, FeeSnapshot
from monik.domain.models.gas import Gas, GasPrice
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId, TokenAddress
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database
from monik.infrastructure.db.types import (
    from_decimal,
    from_timestamp,
    to_decimal,
    to_timestamp,
)
from monik.repositories.sqlite.mapping import column, optional_column

__all__ = ["SqliteFeeRepository", "SqliteGasRepository"]

_SNAPSHOT_COLUMNS = (
    "snapshot_id, provider_id, network_id, operation, version, created_at, expires_at"
)
_RECORD_COLUMNS = (
    "record_id, snapshot_id, fee_type, status, amount, currency, inclusion, source, "
    "observed_at, expires_at, description"
)
_GAS_COLUMNS = (
    "snapshot_id, network_id, status, gas_units, wei_per_gas, base_fee_wei, "
    "priority_fee_wei, native_token, cost_native, source, observed_at, expires_at"
)


def _token_to_text(token: TokenKey | None) -> str | None:
    return str(token) if token else None


def _token_from_text(value: object) -> TokenKey | None:
    if not value:
        return None
    network, _, address = str(value).partition(":")
    return TokenKey(network_id=NetworkId(network), address=TokenAddress(address))


class SqliteFeeRepository:
    """Persistence снимков комиссий (``38_INTERFACES.md`` §73).

    Неизвестная комиссия сохраняется со статусом ``UNKNOWN`` и **без** суммы:
    подставлять ноль запрещено (``07_FEE_SYSTEM.md`` §15).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def save(self, snapshot: FeeSnapshot) -> None:
        """Сохранить снимок вместе с его компонентами атомарно."""
        async with self._database.transaction() as tx:
            await tx.execute(
                f"INSERT INTO fee_snapshots ({_SNAPSHOT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.provider_id.value,
                    str(snapshot.network_id),
                    snapshot.operation.value,
                    snapshot.version,
                    to_timestamp(snapshot.created_at),
                    None,
                ),
            )
            # Идентификатор записи детерминирован и отражает позицию в снимке:
            # порядок компонентов при чтении обязан совпадать с исходным.
            for index, fee in enumerate(snapshot.fees):
                await tx.execute(
                    f"INSERT INTO fee_records ({_RECORD_COLUMNS}) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"{snapshot.snapshot_id}-{index:04d}",
                        snapshot.snapshot_id,
                        fee.fee_type.value,
                        fee.status.value,
                        to_decimal(fee.amount) if fee.amount is not None else None,
                        _token_to_text(fee.currency),
                        fee.inclusion.value,
                        fee.source,
                        to_timestamp(fee.observed_at),
                        to_timestamp(fee.expires_at) if fee.expires_at else None,
                        fee.description,
                    ),
                )

    async def latest(
        self,
        provider_id: ProviderId,
        network_id: NetworkId,
        operation: OperationType,
    ) -> FeeSnapshot | None:
        """Самый свежий снимок для контекста."""
        row = await self._database.fetch_one(
            f"SELECT {_SNAPSHOT_COLUMNS} FROM fee_snapshots WHERE provider_id = ? "
            "AND network_id = ? AND operation = ? ORDER BY created_at DESC, version DESC LIMIT 1",
            (provider_id.value, str(network_id), operation.value),
        )
        if row is None:
            return None
        return await self._to_domain(row)

    async def get(self, snapshot_id: str) -> FeeSnapshot | None:
        """Снимок по идентификатору."""
        row = await self._database.fetch_one(
            f"SELECT {_SNAPSHOT_COLUMNS} FROM fee_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        return await self._to_domain(row) if row else None

    async def delete_created_before(self, moment: UtcDatetime) -> int:
        """Удалить устаревшие снимки (retention, ``07_FEE_SYSTEM.md`` §55)."""
        rows = await self._database.fetch_all(
            "SELECT snapshot_id FROM fee_snapshots WHERE created_at < ?",
            (to_timestamp(moment),),
        )
        if not rows:
            return 0
        await self._database.execute(
            "DELETE FROM fee_snapshots WHERE created_at < ?", (to_timestamp(moment),)
        )
        return len(rows)

    async def _to_domain(self, row: aiosqlite.Row) -> FeeSnapshot:
        snapshot_id = str(column(row, "snapshot_id"))
        records = await self._database.fetch_all(
            f"SELECT {_RECORD_COLUMNS} FROM fee_records WHERE snapshot_id = ? ORDER BY record_id",
            (snapshot_id,),
        )
        return FeeSnapshot(
            snapshot_id=snapshot_id,
            provider_id=ProviderId(str(column(row, "provider_id"))),
            network_id=NetworkId(str(column(row, "network_id"))),
            operation=OperationType(str(column(row, "operation"))),
            fees=tuple(self._fee_to_domain(record) for record in records),
            version=int(column(row, "version")),
            created_at=from_timestamp(str(column(row, "created_at"))),
        )

    @staticmethod
    def _fee_to_domain(row: aiosqlite.Row) -> Fee:
        amount = optional_column(row, "amount")
        expires_at = optional_column(row, "expires_at")
        return Fee(
            fee_type=FeeType(str(column(row, "fee_type"))),
            status=FeeStatus(str(column(row, "status"))),
            amount=from_decimal(str(amount)) if amount is not None else None,
            currency=_token_from_text(optional_column(row, "currency")),
            inclusion=CostInclusion(str(column(row, "inclusion"))),
            source=str(column(row, "source")),
            observed_at=from_timestamp(str(column(row, "observed_at"))),
            expires_at=from_timestamp(str(expires_at)) if expires_at else None,
            description=optional_column(row, "description"),
        )


class SqliteGasRepository:
    """Persistence снимков gas.

    Неизвестный gas сохраняется без стоимости: он не эквивалентен нулю
    (``09_PROFIT_CALCULATOR.md`` §16).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def save(self, gas: Gas, *, snapshot_id: str | None = None) -> str:
        """Сохранить снимок gas и вернуть его идентификатор."""
        identifier = snapshot_id or str(uuid.uuid4())
        price = gas.gas_price
        await self._database.execute(
            f"INSERT INTO gas_snapshots ({_GAS_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identifier,
                str(gas.network_id),
                gas.status.value,
                gas.gas_units,
                str(price.wei_per_gas) if price else None,
                str(price.base_fee_wei) if price and price.base_fee_wei is not None else None,
                str(price.priority_fee_wei)
                if price and price.priority_fee_wei is not None
                else None,
                _token_to_text(gas.native_token),
                to_decimal(gas.cost_native) if gas.cost_native is not None else None,
                gas.source,
                to_timestamp(gas.observed_at),
                to_timestamp(price.expires_at) if price and price.expires_at else None,
            ),
        )
        return identifier

    async def latest(self, network_id: NetworkId) -> Gas | None:
        """Самый свежий снимок gas сети."""
        row = await self._database.fetch_one(
            f"SELECT {_GAS_COLUMNS} FROM gas_snapshots WHERE network_id = ? "
            "ORDER BY observed_at DESC LIMIT 1",
            (str(network_id),),
        )
        return self._to_domain(row) if row else None

    async def delete_observed_before(self, moment: UtcDatetime) -> int:
        """Удалить устаревшие снимки gas."""
        rows = await self._database.fetch_all(
            "SELECT snapshot_id FROM gas_snapshots WHERE observed_at < ?",
            (to_timestamp(moment),),
        )
        if not rows:
            return 0
        await self._database.execute(
            "DELETE FROM gas_snapshots WHERE observed_at < ?", (to_timestamp(moment),)
        )
        return len(rows)

    @staticmethod
    def _to_domain(row: aiosqlite.Row) -> Gas:
        network_id = NetworkId(str(column(row, "network_id")))
        wei_per_gas = optional_column(row, "wei_per_gas")
        base_fee = optional_column(row, "base_fee_wei")
        priority_fee = optional_column(row, "priority_fee_wei")
        cost_native = optional_column(row, "cost_native")
        expires_at = optional_column(row, "expires_at")
        gas_price = (
            GasPrice(
                network_id=network_id,
                wei_per_gas=int(wei_per_gas),
                base_fee_wei=int(base_fee) if base_fee is not None else None,
                priority_fee_wei=int(priority_fee) if priority_fee is not None else None,
                source=str(column(row, "source")),
                observed_at=from_timestamp(str(column(row, "observed_at"))),
                expires_at=from_timestamp(str(expires_at)) if expires_at else None,
            )
            if wei_per_gas is not None
            else None
        )
        gas_units = optional_column(row, "gas_units")
        return Gas(
            network_id=network_id,
            status=FeeStatus(str(column(row, "status"))),
            gas_units=int(gas_units) if gas_units is not None else None,
            gas_price=gas_price,
            native_token=_token_from_text(optional_column(row, "native_token")),
            cost_native=from_decimal(str(cost_native)) if cost_native is not None else None,
            observed_at=from_timestamp(str(column(row, "observed_at"))),
            source=str(column(row, "source")),
        )
