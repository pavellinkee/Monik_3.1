"""Хранилище Opportunity — сущности, создаваемой Level 1."""

from __future__ import annotations

import aiosqlite

from monik.domain.enums.lifecycle import OpportunityStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DatabaseError
from monik.domain.models.job import Level2Job
from monik.domain.models.opportunity import Opportunity, OpportunityAmount, RouteSnapshot
from monik.domain.models.profit import ProfitResult
from monik.domain.models.route import Route
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.fingerprints import OpportunityFingerprint
from monik.domain.value_objects.identifiers import OpportunityId, ScanId, VId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database, Transaction
from monik.infrastructure.db.types import (
    from_raw_amount,
    from_timestamp,
    to_raw_amount,
    to_timestamp,
)
from monik.repositories.sqlite.jobs import insert_job
from monik.repositories.sqlite.mapping import column, dump_model, load_model, optional_column

__all__ = ["SqliteOpportunityRepository"]

_COLUMNS = (
    "opportunity_id, v_id, scan_id, status, fingerprint, network_id, input_token, "
    "intermediate_token, output_token, buy_provider_id, sell_provider_id, "
    "buy_route_json, sell_route_json, buy_route_fingerprint, sell_route_fingerprint, "
    "detected_at, expires_at, updated_at, confirmed_at, formula_version"
)

_AMOUNT_COLUMNS = (
    "opportunity_id, raw_input_amount, input_decimals, preliminary_buy_output, "
    "preliminary_sell_output, buy_output_decimals, preliminary_net_profit, "
    "preliminary_net_roi, preliminary_status, confirmation_status, preliminary_result_json"
)

#: Статусы, в которых возможность ещё ожидает или проходит проверку.
_ACTIVE_STATUSES = (OpportunityStatus.CREATED.value, OpportunityStatus.VERIFYING.value)


class SqliteOpportunityRepository:
    """Сохраняет Opportunity, её amount-контексты и связанный Level 2 Job."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_with_job(self, opportunity: Opportunity, job: Level2Job) -> None:
        """Атомарно сохранить возможность, её суммы и Level 2 Job."""
        if job.opportunity_id != opportunity.opportunity_id:
            raise DatabaseError(
                "level 2 job does not belong to the opportunity being created",
                code="database_inconsistent_write",
            )
        async with self._database.transaction() as tx:
            await self._insert_opportunity(tx, opportunity)
            await self._insert_amounts(tx, opportunity)
            await insert_job(tx, job)

    async def get(self, opportunity_id: OpportunityId) -> Opportunity | None:
        """Найти по внутреннему идентификатору."""
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM opportunities WHERE opportunity_id = ?",
            (str(opportunity_id),),
        )
        return await self._to_domain(row) if row else None

    async def get_by_v_id(self, v_id: VId) -> Opportunity | None:
        """Найти по публичному идентификатору ``#V``."""
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM opportunities WHERE v_id = ?", (str(v_id),)
        )
        return await self._to_domain(row) if row else None

    async def find_recent_by_fingerprint(
        self, fingerprint: OpportunityFingerprint, *, since: UtcDatetime
    ) -> Opportunity | None:
        """Найти логически такую же возможность в окне дедупликации.

        Отпечаток не зависит от случайного идентификатора, поэтому пригоден
        для дедупликации (``10_LEVEL_1_SCANNER.md`` §53).
        """
        row = await self._database.fetch_one(
            f"SELECT {_COLUMNS} FROM opportunities WHERE fingerprint = ? AND detected_at >= ? "
            "ORDER BY detected_at DESC LIMIT 1",
            (str(fingerprint), to_timestamp(since)),
        )
        return await self._to_domain(row) if row else None

    async def update_status(
        self,
        opportunity_id: OpportunityId,
        status: OpportunityStatus,
        *,
        updated_at: UtcDatetime,
        confirmed_at: UtcDatetime | None = None,
    ) -> None:
        """Изменить статус возможности.

        Финансовые значения не изменяются: снимок остаётся неизменным
        (``35_STATE_MACHINES.md`` §66).
        """
        await self._database.execute(
            "UPDATE opportunities SET status = ?, updated_at = ?, "
            "confirmed_at = COALESCE(?, confirmed_at) WHERE opportunity_id = ?",
            (
                status.value,
                to_timestamp(updated_at),
                to_timestamp(confirmed_at) if confirmed_at else None,
                str(opportunity_id),
            ),
        )

    async def list_by_status(
        self, status: OpportunityStatus, *, limit: int
    ) -> tuple[Opportunity, ...]:
        """Возможности в указанном статусе, начиная с самых ранних."""
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM opportunities WHERE status = ? ORDER BY detected_at LIMIT ?",
            (status.value, limit),
        )
        return tuple([await self._to_domain(row) for row in rows])

    async def list_expired(self, *, now: UtcDatetime, limit: int) -> tuple[Opportunity, ...]:
        """Незавершённые возможности, у которых истёк срок проверки."""
        placeholders = ", ".join("?" for _ in _ACTIVE_STATUSES)
        rows = await self._database.fetch_all(
            f"SELECT {_COLUMNS} FROM opportunities WHERE expires_at <= ? "
            f"AND status IN ({placeholders}) ORDER BY expires_at LIMIT ?",
            (to_timestamp(now), *_ACTIVE_STATUSES, limit),
        )
        return tuple([await self._to_domain(row) for row in rows])

    # --- запись -----------------------------------------------------------

    @staticmethod
    async def _insert_opportunity(tx: Transaction, opportunity: Opportunity) -> None:
        routes = opportunity.routes
        await tx.execute(
            f"INSERT INTO opportunities ({_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(opportunity.opportunity_id),
                str(opportunity.v_id),
                str(opportunity.scan_id),
                opportunity.status.value,
                str(opportunity.fingerprint),
                str(opportunity.network_id),
                str(opportunity.input_token),
                str(opportunity.intermediate_token),
                str(opportunity.output_token),
                opportunity.buy_provider_id.value,
                opportunity.sell_provider_id.value,
                dump_model(routes.buy_route),
                dump_model(routes.sell_route),
                str(routes.buy_route.fingerprint),
                str(routes.sell_route.fingerprint),
                to_timestamp(opportunity.detected_at),
                to_timestamp(opportunity.expires_at),
                to_timestamp(opportunity.updated_at) if opportunity.updated_at else None,
                None,
                opportunity.amounts[0].preliminary_result.formula_version,
            ),
        )

    @staticmethod
    async def _insert_amounts(tx: Transaction, opportunity: Opportunity) -> None:
        for amount in opportunity.amounts:
            result = amount.preliminary_result
            await tx.execute(
                f"INSERT INTO opportunity_amounts ({_AMOUNT_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(opportunity.opportunity_id),
                    to_raw_amount(amount.input_amount.raw),
                    amount.input_amount.decimals,
                    to_raw_amount(amount.preliminary_buy_output.raw),
                    to_raw_amount(amount.preliminary_sell_output.raw),
                    amount.preliminary_buy_output.decimals,
                    str(result.net_profit) if result.net_profit is not None else None,
                    str(result.net_roi.value) if result.net_roi is not None else None,
                    result.status.value,
                    None,
                    dump_model(result),
                ),
            )

    # --- чтение -----------------------------------------------------------

    async def _to_domain(self, row: aiosqlite.Row) -> Opportunity:
        opportunity_id = OpportunityId(str(column(row, "opportunity_id")))
        amounts = await self._load_amounts(opportunity_id)
        scan_id = optional_column(row, "scan_id")
        if scan_id is None:
            raise DatabaseError(
                f"opportunity {opportunity_id} lost its scan reference",
                code="database_row_incomplete",
            )
        updated_at = optional_column(row, "updated_at")
        return Opportunity(
            opportunity_id=opportunity_id,
            v_id=VId(str(column(row, "v_id"))),
            scan_id=ScanId(str(scan_id)),
            status=OpportunityStatus(str(column(row, "status"))),
            buy_provider_id=ProviderId(str(column(row, "buy_provider_id"))),
            sell_provider_id=ProviderId(str(column(row, "sell_provider_id"))),
            routes=RouteSnapshot(
                buy_route=load_model(Route, column(row, "buy_route_json")),
                sell_route=load_model(Route, column(row, "sell_route_json")),
            ),
            amounts=amounts,
            detected_at=from_timestamp(str(column(row, "detected_at"))),
            expires_at=from_timestamp(str(column(row, "expires_at"))),
            updated_at=from_timestamp(str(updated_at)) if updated_at else None,
        )

    async def _load_amounts(self, opportunity_id: OpportunityId) -> tuple[OpportunityAmount, ...]:
        rows = await self._database.fetch_all(
            f"SELECT {_AMOUNT_COLUMNS} FROM opportunity_amounts WHERE opportunity_id = ? "
            # Суммы хранятся как TEXT, поэтому численный порядок задаётся
            # сначала длиной, затем лексикографически.
            "ORDER BY LENGTH(raw_input_amount), raw_input_amount",
            (str(opportunity_id),),
        )
        if not rows:
            raise DatabaseError(
                f"opportunity {opportunity_id} has no amount contexts",
                code="database_row_incomplete",
            )
        return tuple(self._amount_to_domain(row) for row in rows)

    @staticmethod
    def _amount_to_domain(row: aiosqlite.Row) -> OpportunityAmount:
        decimals = int(column(row, "input_decimals"))
        return OpportunityAmount(
            input_amount=TokenAmount(
                raw=from_raw_amount(str(column(row, "raw_input_amount"))),
                decimals=decimals,
            ),
            preliminary_result=load_model(ProfitResult, column(row, "preliminary_result_json")),
            preliminary_buy_output=TokenAmount(
                raw=from_raw_amount(str(column(row, "preliminary_buy_output"))),
                decimals=int(column(row, "buy_output_decimals")),
            ),
            preliminary_sell_output=TokenAmount(
                raw=from_raw_amount(str(column(row, "preliminary_sell_output"))),
                decimals=decimals,
            ),
        )
