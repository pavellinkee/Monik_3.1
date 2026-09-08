"""Level 2 Job, его попытки и результаты проверки сумм."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.lifecycle import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
)
from monik.domain.enums.resources import RequestPriority
from monik.domain.models.base import DomainModel
from monik.domain.models.fee import FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.profit import ProfitResult
from monik.domain.models.quote import Quote
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.identifiers import KId, OpportunityId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = [
    "AmountVerificationResult",
    "ConfirmationResult",
    "Level2Attempt",
    "Level2Job",
]

#: Отображение результата проверки суммы в confirmation-статус ``CLAUDE.md`` §26.
#: ``PARTIAL`` исключается из confirmation rate (``CLAUDE.md`` §27), поэтому
#: неопределённые результаты не смешиваются с подтверждёнными и опровергнутыми.
_CONFIRMATION_MAPPING: dict[AmountVerificationStatus, AmountConfirmationStatus] = {
    AmountVerificationStatus.VERIFIED_PROFITABLE: AmountConfirmationStatus.CONFIRMED,
    AmountVerificationStatus.VERIFIED_UNPROFITABLE: AmountConfirmationStatus.UNCONFIRMED,
    AmountVerificationStatus.UNKNOWN: AmountConfirmationStatus.PARTIAL,
    AmountVerificationStatus.FAILED: AmountConfirmationStatus.PARTIAL,
    AmountVerificationStatus.EXPIRED: AmountConfirmationStatus.PARTIAL,
    AmountVerificationStatus.ROUTE_UNAVAILABLE: AmountConfirmationStatus.PARTIAL,
}


class AmountVerificationResult(DomainModel):
    """Результат Level 2 проверки одной суммы (``11_LEVEL_2_SCANNER.md`` §8, §48).

    SELL проверяется на **текущем** BUY output, а не на значении Level 1
    (``11_LEVEL_2_SCANNER.md`` §16-17), поэтому оба значения хранятся здесь.
    """

    input_amount: TokenAmount
    status: AmountVerificationStatus
    buy_quote: Quote | None = None
    sell_quote: Quote | None = None
    current_buy_output: TokenAmount | None = None
    current_sell_output: TokenAmount | None = None
    fee_snapshots: tuple[FeeSnapshot, ...] = ()
    gas: Gas | None = None
    profit_result: ProfitResult | None = None
    rejection_reason: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Проверенный результат обязан содержать данные, на которых он получен."""
        verified = {
            AmountVerificationStatus.VERIFIED_PROFITABLE,
            AmountVerificationStatus.VERIFIED_UNPROFITABLE,
        }
        if self.status in verified:
            missing = [
                name
                for name, value in (
                    ("buy_quote", self.buy_quote),
                    ("sell_quote", self.sell_quote),
                    ("current_buy_output", self.current_buy_output),
                    ("current_sell_output", self.current_sell_output),
                    ("profit_result", self.profit_result),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"verified amount result is missing: {', '.join(missing)}; "
                    "verification must be based on fresh data"
                )
        if (
            self.status is AmountVerificationStatus.VERIFIED_PROFITABLE
            and self.profit_result is not None
            and not self.profit_result.is_profitable
        ):
            raise ValueError(
                "amount cannot be VERIFIED_PROFITABLE while the calculation "
                "is incomplete or below threshold"
            )
        if self.sell_quote is not None and self.current_buy_output is not None:
            if self.sell_quote.input_amount != self.current_buy_output:
                raise ValueError(
                    "sell quote must be requested for the current buy output, "
                    "not for a stale intermediate amount"
                )
        return self

    @property
    def confirmation_status(self) -> AmountConfirmationStatus:
        """Confirmation-статус суммы в терминах ``CLAUDE.md`` §26."""
        return _CONFIRMATION_MAPPING[self.status]


class Level2Attempt(DomainModel):
    """Одна попытка проверки внутри Job (``11_LEVEL_2_SCANNER.md`` §71).

    Retry создаёт новый attempt внутри существующего K-ID, а не новый Job
    (``04_SCHEDULER.md`` §24).
    """

    revision: int = Field(ge=1)
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None
    status: JobStatus
    amount_results: tuple[AmountVerificationResult, ...] = ()
    error_code: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("attempt finished_at must not precede started_at")
        return self


class Level2Job(DomainModel):
    """Единица подтверждения одной Opportunity (``36_DATA_MODELS.md`` §36).

    Job принадлежит Level 2: другие подсистемы не изменяют его статус напрямую
    (``36_DATA_MODELS.md`` §37). ``attempt_count`` не означает успешного
    выполнения (``36_DATA_MODELS.md`` §39).
    """

    k_id: KId
    opportunity_id: OpportunityId
    status: JobStatus
    priority: RequestPriority = RequestPriority.LEVEL2
    attempt_count: int = Field(default=0, ge=0)
    created_at: UtcDatetime
    updated_at: UtcDatetime
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("job expires_at must be after created_at")
        if self.updated_at < self.created_at:
            raise ValueError("job updated_at must not precede created_at")
        return self

    def is_expired(self, now: UtcDatetime) -> bool:
        """Истёк ли срок, в течение которого Job можно выполнять.

        Expiration имеет приоритет над retry (``35_STATE_MACHINES.md`` §40).
        """
        return now >= self.expires_at

    @property
    def is_terminal(self) -> bool:
        """Является ли текущий статус терминальным (``35_STATE_MACHINES.md`` §26-37)."""
        return self.status in {
            JobStatus.CONFIRMED,
            JobStatus.REJECTED,
            JobStatus.FAILED,
            JobStatus.EXPIRED,
            JobStatus.CANCELLED,
        }


class ConfirmationResult(DomainModel):
    """Итог одной проверки Level 2 (``36_DATA_MODELS.md`` §40).

    Confirmation Result не является Opportunity (``36_DATA_MODELS.md`` §41):
    он описывает результат проверки, на основании которого Opportunity
    переводится в соответствующий статус.
    """

    k_id: KId
    opportunity_id: OpportunityId
    revision: int = Field(ge=1)
    job_status: JobStatus
    amount_results: tuple[AmountVerificationResult, ...] = Field(min_length=1)
    completed_at: UtcDatetime
    failure_reason: str | None = Field(default=None, max_length=256)

    @property
    def confirmed_count(self) -> int:
        """Число сумм со статусом ``CONFIRMED``."""
        return sum(
            1
            for result in self.amount_results
            if result.confirmation_status is AmountConfirmationStatus.CONFIRMED
        )

    @property
    def unconfirmed_count(self) -> int:
        """Число сумм со статусом ``UNCONFIRMED``."""
        return sum(
            1
            for result in self.amount_results
            if result.confirmation_status is AmountConfirmationStatus.UNCONFIRMED
        )

    @property
    def partial_count(self) -> int:
        """Число сумм со статусом ``PARTIAL``."""
        return sum(
            1
            for result in self.amount_results
            if result.confirmation_status is AmountConfirmationStatus.PARTIAL
        )

    @property
    def has_confirmed_amount(self) -> bool:
        """Подтверждена ли хотя бы одна сумма.

        Согласно ``CLAUDE.md`` §26 наличие подтверждённой суммы позволяет
        считать Opportunity подтверждённой; ``PARTIAL`` таким основанием
        не является.
        """
        return self.confirmed_count > 0
