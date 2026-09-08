"""Хранилище Level 2 Job, его попыток и результатов проверки сумм."""

from __future__ import annotations

import uuid

import aiosqlite

from monik.domain.enums.lifecycle import AmountVerificationStatus, JobStatus
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import DatabaseError
from monik.domain.models.fee import FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.job import (
    AmountVerificationResult,
    ConfirmationResult,
    Level2Attempt,
    Level2Job,
)
from monik.domain.models.profit import ProfitResult
from monik.domain.models.quote import Quote
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.identifiers import KId, OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.db.connection import Database, Transaction
from monik.infrastructure.db.types import (
    from_json,
    from_raw_amount,
    from_timestamp,
    to_json,
    to_raw_amount,
    to_timestamp,
)
from monik.repositories.sqlite.mapping import column, dump_model, load_model, optional_column

__all__ = ["SqliteJobRepository", "insert_job"]

_JOB_COLUMNS = (
    "k_id, opportunity_id, status, priority, attempt_count, created_at, updated_at, expires_at"
)

_RESULT_COLUMNS = (
    "result_id, attempt_id, raw_input_amount, input_decimals, status, confirmation_status, "
    "current_buy_output, current_sell_output, gross_profit, gross_roi, total_fees, gas_cost, "
    "other_costs, rebates, net_profit, net_roi, threshold, threshold_passed, "
    "calculation_status, formula_version, fee_snapshot_json, gas_snapshot_json, "
    "calculation_json, rejection_reason, created_at, buy_quote_json, sell_quote_json"
)

#: Статусы, при которых котировки сохраняются как подтверждение решения.
_VERIFIED_STATUSES = frozenset(
    {
        AmountVerificationStatus.VERIFIED_PROFITABLE,
        AmountVerificationStatus.VERIFIED_UNPROFITABLE,
    }
)


async def insert_job(tx: Transaction, job: Level2Job) -> None:
    """Вставить Job внутри существующей транзакции.

    Вынесено отдельной функцией, чтобы создание Opportunity и её Job
    выполнялось атомарно (``CLAUDE.md`` §29).
    """
    await tx.execute(
        f"INSERT INTO level2_jobs ({_JOB_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(job.k_id),
            str(job.opportunity_id),
            job.status.value,
            job.priority.value,
            job.attempt_count,
            to_timestamp(job.created_at),
            to_timestamp(job.updated_at),
            to_timestamp(job.expires_at),
        ),
    )


class SqliteJobRepository:
    """Сохраняет Job, его попытки и per-amount результаты."""

    def __init__(self, database: Database) -> None:
        self._database = database

    # --- Job --------------------------------------------------------------

    async def get(self, k_id: KId) -> Level2Job | None:
        """Найти Job по публичному идентификатору."""
        row = await self._database.fetch_one(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE k_id = ?", (str(k_id),)
        )
        return self._job_to_domain(row) if row else None

    async def get_by_opportunity(self, opportunity_id: OpportunityId) -> Level2Job | None:
        """Найти Job возможности."""
        row = await self._database.fetch_one(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE opportunity_id = ?",
            (str(opportunity_id),),
        )
        return self._job_to_domain(row) if row else None

    async def update_status(
        self,
        k_id: KId,
        status: JobStatus,
        *,
        updated_at: UtcDatetime,
        attempt_count: int | None = None,
    ) -> None:
        """Изменить статус Job."""
        await self._database.execute(
            "UPDATE level2_jobs SET status = ?, updated_at = ?, "
            "attempt_count = COALESCE(?, attempt_count) WHERE k_id = ?",
            (status.value, to_timestamp(updated_at), attempt_count, str(k_id)),
        )

    async def claim_queued(self, *, limit: int, now: UtcDatetime) -> tuple[Level2Job, ...]:
        """Взять готовые к выполнению Job'ы в порядке приоритета.

        Порядок определяется приоритетом и временем постановки
        (``04_SCHEDULER.md`` §25); прибыльность на порядок не влияет
        (``04_SCHEDULER.md`` §26).
        """
        rows = await self._database.fetch_all(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE status = ? AND expires_at > ? "
            "ORDER BY priority, created_at LIMIT ?",
            (JobStatus.QUEUED.value, to_timestamp(now), limit),
        )
        return tuple(self._job_to_domain(row) for row in rows)

    async def list_by_status(self, status: JobStatus, *, limit: int) -> tuple[Level2Job, ...]:
        """Job'ы в указанном статусе."""
        rows = await self._database.fetch_all(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE status = ? ORDER BY created_at LIMIT ?",
            (status.value, limit),
        )
        return tuple(self._job_to_domain(row) for row in rows)

    async def list_expired(self, *, now: UtcDatetime, limit: int) -> tuple[Level2Job, ...]:
        """Незавершённые Job'ы с истёкшим сроком."""
        rows = await self._database.fetch_all(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE expires_at <= ? "
            "AND status IN (?, ?) ORDER BY expires_at LIMIT ?",
            (
                to_timestamp(now),
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
                limit,
            ),
        )
        return tuple(self._job_to_domain(row) for row in rows)

    async def list_interrupted(self) -> tuple[Level2Job, ...]:
        """Job'ы, оставшиеся ``RUNNING`` после аварийной остановки."""
        rows = await self._database.fetch_all(
            f"SELECT {_JOB_COLUMNS} FROM level2_jobs WHERE status = ? ORDER BY created_at",
            (JobStatus.RUNNING.value,),
        )
        return tuple(self._job_to_domain(row) for row in rows)

    # --- попытки ----------------------------------------------------------

    async def record_attempt(self, attempt: Level2Attempt, *, k_id: KId) -> str:
        """Сохранить попытку проверки.

        Retry создаёт новый attempt внутри существующего ``#K``, а не новый
        Job (``04_SCHEDULER.md`` §24).
        """
        attempt_id = str(uuid.uuid4())
        await self._database.execute(
            "INSERT INTO level2_attempts (attempt_id, k_id, revision, status, started_at, "
            "finished_at, error_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                attempt_id,
                str(k_id),
                attempt.revision,
                attempt.status.value,
                to_timestamp(attempt.started_at),
                to_timestamp(attempt.finished_at) if attempt.finished_at else None,
                attempt.error_code,
            ),
        )
        return attempt_id

    # --- результаты проверки ---------------------------------------------

    async def save_confirmation(self, result: ConfirmationResult) -> None:
        """Сохранить результат проверки со всеми суммами атомарно."""
        async with self._database.transaction() as tx:
            attempt_id = str(uuid.uuid4())
            await tx.execute(
                "INSERT INTO level2_attempts (attempt_id, k_id, revision, status, started_at, "
                "finished_at, error_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    str(result.k_id),
                    result.revision,
                    result.job_status.value,
                    to_timestamp(result.completed_at),
                    to_timestamp(result.completed_at),
                    result.failure_reason,
                ),
            )
            for amount_result in result.amount_results:
                await self._insert_amount_result(tx, attempt_id, amount_result, result)

    async def load_confirmation(self, k_id: KId, revision: int) -> ConfirmationResult | None:
        """Прочитать сохранённый результат проверки."""
        attempt = await self._database.fetch_one(
            "SELECT attempt_id, k_id, revision, status, started_at, finished_at, error_code "
            "FROM level2_attempts WHERE k_id = ? AND revision = ?",
            (str(k_id), revision),
        )
        if attempt is None:
            return None
        job = await self.get(k_id)
        if job is None:
            raise DatabaseError(
                f"confirmation references missing job {k_id}",
                code="database_row_incomplete",
            )
        rows = await self._database.fetch_all(
            f"SELECT {_RESULT_COLUMNS} FROM level2_amount_results WHERE attempt_id = ? "
            "ORDER BY LENGTH(raw_input_amount), raw_input_amount",
            (str(column(attempt, "attempt_id")),),
        )
        if not rows:
            raise DatabaseError(
                f"confirmation {k_id}/{revision} has no amount results",
                code="database_row_incomplete",
            )
        finished_at = optional_column(attempt, "finished_at")
        return ConfirmationResult(
            k_id=k_id,
            opportunity_id=job.opportunity_id,
            revision=int(column(attempt, "revision")),
            job_status=JobStatus(str(column(attempt, "status"))),
            amount_results=tuple(self._result_to_domain(row) for row in rows),
            completed_at=from_timestamp(
                str(finished_at if finished_at else column(attempt, "started_at"))
            ),
            failure_reason=optional_column(attempt, "error_code"),
        )

    @staticmethod
    async def _insert_amount_result(
        tx: Transaction,
        attempt_id: str,
        amount_result: AmountVerificationResult,
        confirmation: ConfirmationResult,
    ) -> None:
        profit = amount_result.profit_result
        costs = profit.costs if profit else None
        threshold = profit.threshold_outcome if profit else None
        store_quotes = amount_result.status in _VERIFIED_STATUSES
        await tx.execute(
            f"INSERT INTO level2_amount_results ({_RESULT_COLUMNS}) VALUES ("
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                attempt_id,
                to_raw_amount(amount_result.input_amount.raw),
                amount_result.input_amount.decimals,
                amount_result.status.value,
                amount_result.confirmation_status.value,
                _raw_or_none(amount_result.current_buy_output),
                _raw_or_none(amount_result.current_sell_output),
                _text_or_none(profit.gross_profit if profit else None),
                _text_or_none(profit.gross_roi.value if profit and profit.gross_roi else None),
                _text_or_none(costs.total_fees if costs else None),
                _text_or_none(costs.gas_cost if costs else None),
                _text_or_none(costs.other_costs if costs else None),
                _text_or_none(costs.rebates if costs else None),
                _text_or_none(profit.net_profit if profit else None),
                _text_or_none(profit.net_roi.value if profit and profit.net_roi else None),
                _text_or_none(threshold.threshold if threshold else None),
                None if threshold is None else int(threshold.passed),
                profit.status.value if profit else None,
                profit.formula_version if profit else None,
                _dump_snapshots(amount_result.fee_snapshots),
                dump_model(amount_result.gas),
                dump_model(profit),
                amount_result.rejection_reason,
                to_timestamp(confirmation.completed_at),
                dump_model(amount_result.buy_quote) if store_quotes else None,
                dump_model(amount_result.sell_quote) if store_quotes else None,
            ),
        )

    @staticmethod
    def _result_to_domain(row: aiosqlite.Row) -> AmountVerificationResult:
        decimals = int(column(row, "input_decimals"))
        buy_quote_json = optional_column(row, "buy_quote_json")
        sell_quote_json = optional_column(row, "sell_quote_json")
        buy_output = optional_column(row, "current_buy_output")
        sell_output = optional_column(row, "current_sell_output")
        calculation = optional_column(row, "calculation_json")
        gas_json = optional_column(row, "gas_snapshot_json")
        fee_json = optional_column(row, "fee_snapshot_json")
        buy_quote = load_model(Quote, buy_quote_json) if buy_quote_json else None
        return AmountVerificationResult(
            input_amount=TokenAmount(
                raw=from_raw_amount(str(column(row, "raw_input_amount"))), decimals=decimals
            ),
            status=AmountVerificationStatus(str(column(row, "status"))),
            buy_quote=buy_quote,
            sell_quote=load_model(Quote, sell_quote_json) if sell_quote_json else None,
            current_buy_output=(
                TokenAmount(
                    raw=from_raw_amount(str(buy_output)),
                    decimals=buy_quote.output_amount.decimals if buy_quote else decimals,
                )
                if buy_output
                else None
            ),
            current_sell_output=(
                TokenAmount(raw=from_raw_amount(str(sell_output)), decimals=decimals)
                if sell_output
                else None
            ),
            fee_snapshots=_load_snapshots(fee_json),
            gas=load_model(Gas, gas_json) if gas_json else None,
            profit_result=load_model(ProfitResult, calculation) if calculation else None,
            rejection_reason=optional_column(row, "rejection_reason"),
        )

    @staticmethod
    def _job_to_domain(row: aiosqlite.Row) -> Level2Job:
        return Level2Job(
            k_id=KId(str(column(row, "k_id"))),
            opportunity_id=OpportunityId(str(column(row, "opportunity_id"))),
            status=JobStatus(str(column(row, "status"))),
            priority=RequestPriority(str(column(row, "priority"))),
            attempt_count=int(column(row, "attempt_count")),
            created_at=from_timestamp(str(column(row, "created_at"))),
            updated_at=from_timestamp(str(column(row, "updated_at"))),
            expires_at=from_timestamp(str(column(row, "expires_at"))),
        )


def _raw_or_none(amount: TokenAmount | None) -> str | None:
    return to_raw_amount(amount.raw) if amount else None


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _dump_snapshots(snapshots: tuple[FeeSnapshot, ...]) -> str | None:
    """Сохранить набор fee snapshots одной колонкой."""
    if not snapshots:
        return None
    return to_json([snapshot.model_dump(mode="json") for snapshot in snapshots])


def _load_snapshots(value: object) -> tuple[FeeSnapshot, ...]:
    """Восстановить набор fee snapshots."""
    if not value:
        return ()
    parsed = from_json(str(value))
    if not isinstance(parsed, list):
        raise DatabaseError(
            "stored fee snapshots are not a list",
            code="database_row_invalid",
        )
    return tuple(FeeSnapshot.model_validate(item) for item in parsed)
