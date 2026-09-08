"""Level 2 Scanner — подтверждение возможности на зафиксированном маршруте.

Level 2 отвечает на один вопрос: **сохраняется ли найденная Level 1
возможность сейчас, при актуальных данных, на точно том же маршруте и с
учётом всех известных расходов?** (``11_LEVEL_2_SCANNER.md`` §77).

Он не ищет новый маршрут, не сравнивает агрегаторы, не выполняет
оптимизацию (§61) и не выполняет swap (§3).
"""

from __future__ import annotations

import asyncio
from typing import NoReturn

from monik.config.sections.scanner import Level2Config
from monik.domain.enums.lifecycle import (
    AmountVerificationStatus,
    JobStatus,
    OpportunityStatus,
)
from monik.domain.errors import DomainValidationError
from monik.domain.models.job import (
    AmountVerificationResult,
    ConfirmationResult,
    Level2Job,
)
from monik.domain.models.opportunity import Opportunity
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.services.level2.amounts import AmountVerifier
from monik.services.level2.confirmation import job_status_for, opportunity_status_for
from monik.services.level2.ports import JobStore, OpportunityRegistry
from monik.services.observability import names
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields
from monik.services.observability.metrics import MetricsRegistry

__all__ = ["Level2Scanner"]

_LOGGER = get_logger("services.level2.scanner")


class Level2Scanner:
    """Выполняет одну проверку Level 2 Job."""

    def __init__(
        self,
        config: Level2Config,
        *,
        verifier: AmountVerifier,
        jobs: JobStore,
        opportunities: OpportunityRegistry,
        clock: Clock,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._config = config
        self._verifier = verifier
        self._jobs = jobs
        self._opportunities = opportunities
        self._clock = clock
        self._metrics = metrics

    async def confirm(self, job: Level2Job) -> ConfirmationResult:
        """Проверить Job и вернуть результат.

        Повторная обработка того же Job с той же revision не создаёт
        второй бизнес-результат (§70): сохранённый результат возвращается
        как есть.
        """
        revision = job.attempt_count + 1
        existing = await self._jobs.load_confirmation(job.k_id, revision)
        if existing is not None:
            return existing

        opportunity = await self._opportunities.get(job.opportunity_id)
        with log_context(k_id=str(job.k_id), v_id=_v_id(opportunity)):
            return await self._run(job, opportunity, revision)

    async def _run(
        self, job: Level2Job, opportunity: Opportunity | None, revision: int
    ) -> ConfirmationResult:
        now = self._clock.now()
        if opportunity is None:
            await self._fail_missing_opportunity(job, revision, now=now)
        # Срок проверяется до любых внешних запросов (§26).
        if job.is_expired(now) or opportunity.is_expired(now):
            return await self._expire(job, opportunity, revision, now=now)

        started_at = now
        await self._jobs.update_status(
            job.k_id, JobStatus.RUNNING, updated_at=started_at, attempt_count=revision
        )
        await self._opportunities.update_status(
            opportunity.opportunity_id, OpportunityStatus.VERIFYING, updated_at=started_at
        )

        try:
            async with asyncio.timeout(self._config.confirmation_timeout_seconds):
                results = await self._verify_amounts(opportunity)
        except TimeoutError:
            # Таймаут Job (§27) не является признаком убыточности.
            return await self._fail_all_amounts(
                job,
                opportunity,
                revision,
                reason="level 2 confirmation timed out",
                started_at=started_at,
            )
        except asyncio.CancelledError:
            # Отменённый Job не становится CONFIRMED (§28).
            await self._jobs.update_status(
                job.k_id, JobStatus.CANCELLED, updated_at=self._clock.now()
            )
            await self._opportunities.update_status(
                opportunity.opportunity_id,
                OpportunityStatus.CANCELLED,
                updated_at=self._clock.now(),
            )
            raise

        return await self._finish(job, opportunity, results, revision, started_at=started_at)

    async def _verify_amounts(
        self, opportunity: Opportunity
    ) -> tuple[AmountVerificationResult, ...]:
        """Проверить все суммы возможности.

        Произвольно выбирать только самую прибыльную сумму запрещено (§9).
        Суммы проверяются последовательно: каждая требует собственной пары
        BUY/SELL запросов, а порядок делает результат детерминированным.
        """
        results = []
        for amount in opportunity.amounts:
            results.append(await self._verifier.verify(opportunity, amount))
        return tuple(results)

    async def _finish(
        self,
        job: Level2Job,
        opportunity: Opportunity,
        results: tuple[AmountVerificationResult, ...],
        revision: int,
        *,
        started_at: UtcDatetime,
    ) -> ConfirmationResult:
        completed_at = self._clock.now()
        job_status = job_status_for(results)
        result = ConfirmationResult(
            k_id=job.k_id,
            opportunity_id=job.opportunity_id,
            revision=revision,
            job_status=job_status,
            amount_results=results,
            completed_at=completed_at,
            failure_reason=_failure_reason(results, job_status),
        )
        await self._jobs.save_confirmation(result)
        await self._jobs.update_status(
            job.k_id, job_status, updated_at=completed_at, attempt_count=revision
        )
        opportunity_status = opportunity_status_for(results)
        await self._opportunities.update_status(
            opportunity.opportunity_id,
            opportunity_status,
            updated_at=completed_at,
            confirmed_at=completed_at
            if opportunity_status in {OpportunityStatus.CONFIRMED, OpportunityStatus.PARTIAL}
            else None,
        )
        self._record_metrics(result, started_at=started_at, completed_at=completed_at)
        _LOGGER.info(
            "level 2 confirmation finished",
            extra=log_fields(
                job_status=job_status.value,
                opportunity_status=opportunity_status.value,
                confirmed=result.confirmed_count,
                unconfirmed=result.unconfirmed_count,
                partial=result.partial_count,
                duration_seconds=(completed_at - started_at).total_seconds(),
            ),
        )
        return result

    async def _expire(
        self,
        job: Level2Job,
        opportunity: Opportunity,
        revision: int,
        *,
        now: UtcDatetime,
    ) -> ConfirmationResult:
        """Просроченная возможность не проверяется (§26)."""
        results = tuple(
            AmountVerificationResult(
                input_amount=amount.input_amount,
                status=AmountVerificationStatus.EXPIRED,
                rejection_reason="opportunity expired before level 2 verification",
            )
            for amount in opportunity.amounts
        )
        return await self._finish(job, opportunity, results, revision, started_at=now)

    def _record_metrics(
        self,
        result: ConfirmationResult,
        *,
        started_at: UtcDatetime,
        completed_at: UtcDatetime,
    ) -> None:
        """Метрики подтверждения (``28_OBSERVABILITY.md`` §31).

        Идентификаторы ``#K`` и ``#V`` в labels не попадают (``28`` §42).
        """
        if self._metrics is None:
            return
        self._metrics.increment(names.LEVEL2_JOBS, status=result.job_status.value)
        for amount in result.amount_results:
            self._metrics.increment(names.LEVEL2_AMOUNTS, status=amount.status.value)
        self._metrics.observe(
            names.LEVEL2_SECONDS,
            (completed_at - started_at).total_seconds(),
            status=result.job_status.value,
        )

    async def _fail_all_amounts(
        self,
        job: Level2Job,
        opportunity: Opportunity,
        revision: int,
        *,
        reason: str,
        started_at: UtcDatetime,
    ) -> ConfirmationResult:
        """Все суммы получают ``FAILED``: результат не определён.

        ``FAILED`` не равен ``VERIFIED_UNPROFITABLE``: сбой не является
        доказательством убыточности (``11_LEVEL_2_SCANNER.md`` §53-54).
        """
        results = tuple(
            AmountVerificationResult(
                input_amount=amount.input_amount,
                status=AmountVerificationStatus.FAILED,
                rejection_reason=reason,
            )
            for amount in opportunity.amounts
        )
        return await self._finish(job, opportunity, results, revision, started_at=started_at)

    async def _fail_missing_opportunity(
        self, job: Level2Job, revision: int, *, now: UtcDatetime
    ) -> NoReturn:
        """Job без Opportunity — нарушение целостности, а не результат проверки."""
        reason = f"opportunity {job.opportunity_id} is missing"
        await self._jobs.update_status(
            job.k_id, JobStatus.FAILED, updated_at=now, attempt_count=revision
        )
        _LOGGER.error("level 2 job cannot be verified", extra=log_fields(reason=reason))
        raise DomainValidationError(reason, subsystem="level2", operation=f"confirm:{job.k_id}")


def _failure_reason(
    results: tuple[AmountVerificationResult, ...], job_status: JobStatus
) -> str | None:
    """Причина отрицательного итога, достаточная для восстановления «почему» (§67)."""
    if job_status is JobStatus.CONFIRMED:
        return None
    reasons = [result.rejection_reason for result in results if result.rejection_reason]
    if not reasons:
        return None
    return "; ".join(dict.fromkeys(reasons))[:256]


def _v_id(opportunity: Opportunity | None) -> str | None:
    return str(opportunity.v_id) if opportunity is not None else None
