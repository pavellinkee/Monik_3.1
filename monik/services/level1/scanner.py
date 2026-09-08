"""Level 1 Scanner — оркестрация одного цикла поиска.

Level 1 находит кандидата и фиксирует маршрут; подтверждает его Level 2
(``10_LEVEL_1_SCANNER.md`` §95). Scanner не выполняет swap, не отправляет
Telegram-уведомления, не обходит Resource Manager и не реализует
собственную финансовую формулу (``02_LEVEL1_SCANNER.md`` §96).

Собственного бесконечного таймера у Scanner нет: цикл запускает Scheduler
(``10_LEVEL_1_SCANNER.md`` §65).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from monik.config.root import Configuration
from monik.domain.enums.lifecycle import ScanStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.opportunity import Candidate, Opportunity
from monik.domain.models.scan import Scan, ScanScope, ScanStatistics
from monik.domain.value_objects.identifiers import ScanId
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.services.level1.cycle import TokenCycle
from monik.services.level1.dedup import DeduplicationGuard
from monik.services.level1.filters import CombinationFilter
from monik.services.level1.grouping import CandidateGroup, group_candidates
from monik.services.level1.handoff import OpportunityHandoff
from monik.services.level1.ports import (
    IdSequenceSource,
    Level2Dispatcher,
    OpportunityStore,
    ScanStore,
)
from monik.services.level1.preliminary import PreliminaryEvaluator
from monik.services.level1.quotes import QuoteCollector, QuoteStatistics
from monik.services.level1.ranking import rank_groups
from monik.services.level1.results import ScanResult
from monik.services.level1.scope import ScopeBuilder
from monik.services.observability import names
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields
from monik.services.observability.metrics import MetricsRegistry

__all__ = ["Level1Scanner"]

_LOGGER = get_logger("services.level1.scanner")


class Level1Scanner:
    """Выполняет один цикл Level 1 и передаёт найденные возможности Level 2."""

    def __init__(
        self,
        configuration: Configuration,
        *,
        adapters: dict[ProviderId, AggregatorAdapter],
        scope_builder: ScopeBuilder,
        combinations: CombinationFilter,
        evaluator: PreliminaryEvaluator,
        opportunities: OpportunityStore,
        scans: ScanStore,
        sequences: IdSequenceSource,
        dispatcher: Level2Dispatcher,
        clock: Clock,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._configuration = configuration
        self._adapters = adapters
        self._scope_builder = scope_builder
        self._combinations = combinations
        self._evaluator = evaluator
        self._opportunities = opportunities
        self._scans = scans
        self._sequences = sequences
        self._dispatcher = dispatcher
        self._clock = clock
        self._metrics = metrics

    async def scan(self, scope: ScanScope | None = None) -> ScanResult:
        """Выполнить цикл.

        ``scope`` фиксируется на старте: изменение конфигурации применяется
        со следующего цикла (``02_LEVEL1_SCANNER.md`` §69).
        """
        config = self._configuration.scanner.level1
        scan_scope = scope if scope is not None else self._scope_builder.build()
        scan_id = ScanId.generate()
        started_at = self._clock.now()
        scan = Scan(
            scan_id=scan_id,
            status=ScanStatus.RUNNING,
            scope=scan_scope,
            started_at=started_at,
        )
        collector = QuoteCollector(
            self._adapters,
            self._clock,
            scan_id=scan_id,
            max_age=timedelta(seconds=config.quote_max_age_seconds),
            max_concurrent=config.max_concurrent_requests,
        )
        with log_context(scan_id=str(scan_id)):
            try:
                await self._scans.create(scan)
                return await self._run(scan, scan_scope, collector)
            except asyncio.CancelledError:
                # Частичные результаты отменённого цикла не считаются
                # успешными (``10_LEVEL_1_SCANNER.md`` §67). Обновление
                # безопасно и тогда, когда цикл был отменён до записи строки.
                await self._finish(
                    scan, collector, ScanStatus.CANCELLED, opportunities=(), duplicates=0
                )
                raise

    async def _run(self, scan: Scan, scope: ScanScope, collector: QuoteCollector) -> ScanResult:
        config = self._configuration.scanner.level1
        timed_out = False
        candidates: tuple[Candidate, ...] = ()
        try:
            async with asyncio.timeout(config.scan_timeout_seconds):
                candidates = await self._collect_candidates(scan, scope, collector)
        except TimeoutError:
            # Общий таймаут цикла (``10_LEVEL_1_SCANNER.md`` §68): уже
            # полученные результаты не выбрасываются, но цикл не полон.
            timed_out = True
            _LOGGER.warning("level 1 scan timed out")

        opportunities, duplicates = await self._create_opportunities(scan, candidates)
        status = self._final_status(collector, timed_out=timed_out)
        finished = await self._finish(
            scan, collector, status, opportunities=opportunities, duplicates=duplicates
        )
        return ScanResult(
            scan=finished,
            opportunities=opportunities,
            failures=tuple(
                attempt for attempt in collector.statistics.attempts if not attempt.is_usable
            ),
        )

    async def _collect_candidates(
        self, scan: Scan, scope: ScanScope, collector: QuoteCollector
    ) -> tuple[Candidate, ...]:
        """Запустить независимые циклы токенов параллельно.

        Цикл токена самодостаточен: SELL одного токена не ждёт BUY другого
        (``CLAUDE.md`` §16).
        """
        network_id = scope.networks[0]
        pairs = self._combinations.provider_pairs(
            scope.providers, self._allowed_pairs(scope.providers)
        )
        if not pairs:
            return ()
        cycle = TokenCycle(
            collector=collector,
            combinations=self._combinations,
            evaluator=self._evaluator,
            adapters=self._adapters,
            clock=self._clock,
            scan_id=scan.scan_id,
            network_id=network_id,
            base_token=self._scope_builder.base_token,
            providers=scope.providers,
            pairs=pairs,
            raw_amounts=scope.raw_amounts,
        )
        tokens = [
            token for token in self._scope_builder.scan_tokens() if token.key in set(scope.tokens)
        ]
        results = await asyncio.gather(
            *(cycle.run(token) for token in tokens), return_exceptions=True
        )
        candidates: list[Candidate] = []
        for token, outcome in zip(tokens, results, strict=True):
            if isinstance(outcome, BaseException):
                if isinstance(outcome, asyncio.CancelledError):
                    raise outcome
                # Ошибка одного токена не останавливает остальные (§75).
                _LOGGER.warning(
                    "token cycle failed",
                    extra=log_fields(token=str(token.key), error=type(outcome).__name__),
                )
                continue
            candidates.extend(outcome)
        return tuple(candidates)

    def _allowed_pairs(
        self, providers: tuple[ProviderId, ...]
    ) -> tuple[tuple[ProviderId, ProviderId], ...]:
        """Пары провайдеров, разрешённые route policy."""
        policy = self._configuration.routes
        return tuple(
            (buy, sell) for buy in providers for sell in providers if policy.is_allowed(buy, sell)
        )

    async def _create_opportunities(
        self, scan: Scan, candidates: tuple[Candidate, ...]
    ) -> tuple[tuple[Opportunity, ...], int]:
        """Создать Opportunity из кандидатов, прошедших порог."""
        config = self._configuration.scanner.level1
        qualified = tuple(
            candidate for candidate in candidates if _passes_preliminary_threshold(candidate)
        )
        groups = rank_groups(group_candidates(qualified))
        guard = DeduplicationGuard(
            self._opportunities,
            window=timedelta(seconds=config.deduplication_window_seconds),
        )
        handoff = OpportunityHandoff(
            store=self._opportunities,
            sequences=self._sequences,
            dispatcher=self._dispatcher,
            clock=self._clock,
            opportunity_ttl=timedelta(seconds=config.opportunity_ttl_seconds),
            job_ttl=timedelta(seconds=self._configuration.scanner.level2.job_ttl_seconds),
        )
        capacity = min(config.max_opportunities_per_scan, self._dispatcher.available_capacity())
        created: list[Opportunity] = []
        for group in groups:
            if len(created) >= capacity:
                # Backpressure: бесконечная очередь Job не создаётся (§47).
                break
            opportunity = await self._create_one(group, scan, guard, handoff)
            if opportunity is not None:
                created.append(opportunity)
        return tuple(created), guard.duplicates

    async def _create_one(
        self,
        group: CandidateGroup,
        scan: Scan,
        guard: DeduplicationGuard,
        handoff: OpportunityHandoff,
    ) -> Opportunity | None:
        now = self._clock.now()
        if await guard.is_duplicate(group.fingerprint, now=now):
            return None
        try:
            opportunity = await handoff.create(group, scan_id=scan.scan_id)
        except Exception as error:  # noqa: BLE001 - ошибка фиксируется и цикл продолжается
            # Неполная Opportunity не должна продолжать workflow (§92).
            _LOGGER.error(
                "opportunity creation failed",
                extra=log_fields(error=type(error).__name__, detail=str(error)),
            )
            return None
        guard.remember(opportunity.fingerprint)
        return opportunity

    def _final_status(self, collector: QuoteCollector, *, timed_out: bool) -> ScanStatus:
        statistics = collector.statistics
        if timed_out:
            return ScanStatus.PARTIAL if statistics.successful else ScanStatus.FAILED
        if statistics.requests == 0:
            return ScanStatus.COMPLETE
        if statistics.failed and statistics.successful:
            return ScanStatus.PARTIAL
        if statistics.failed:
            return ScanStatus.FAILED
        return ScanStatus.COMPLETE

    async def _finish(
        self,
        scan: Scan,
        collector: QuoteCollector,
        status: ScanStatus,
        *,
        opportunities: tuple[Opportunity, ...],
        duplicates: int,
    ) -> Scan:
        statistics = collector.statistics
        finished = scan.replace(
            status=status,
            finished_at=self._clock.now(),
            statistics=ScanStatistics(
                quote_requests=statistics.requests,
                successful_quotes=statistics.successful,
                failed_quotes=statistics.failed,
                skipped_combinations=statistics.skipped,
                opportunities_created=len(opportunities),
                duplicate_opportunities=duplicates,
            ),
        )
        await self._scans.update(finished)
        self._record_metrics(finished, statistics)
        _LOGGER.info(
            "level 1 scan finished",
            extra=log_fields(
                status=status.value,
                requests=statistics.requests,
                successful=statistics.successful,
                failed=statistics.failed,
                opportunities=len(opportunities),
            ),
        )
        return finished

    def _record_metrics(self, scan: Scan, statistics: QuoteStatistics) -> None:
        """Записать метрики цикла (``28_OBSERVABILITY.md`` §30).

        В labels попадают только low-cardinality значения: идентификаторы
        цикла и возможностей туда не входят (``28`` §42).
        """
        if self._metrics is None:
            return
        self._metrics.increment(names.LEVEL1_SCANS, status=scan.status.value)
        self._metrics.increment(
            names.LEVEL1_QUOTE_REQUESTS, amount=statistics.requests, status="total"
        )
        self._metrics.increment(
            names.LEVEL1_QUOTE_FAILURES, amount=statistics.failed, status="failed"
        )
        self._metrics.increment(
            names.LEVEL1_OPPORTUNITIES,
            amount=scan.statistics.opportunities_created,
            status="created",
        )
        if scan.finished_at is not None:
            self._metrics.observe(
                names.LEVEL1_SCAN_SECONDS,
                (scan.finished_at - scan.started_at).total_seconds(),
                status=scan.status.value,
            )


def _passes_preliminary_threshold(candidate: Candidate) -> bool:
    """Прошёл ли кандидат предварительный порог.

    Порог применяет Profit Calculator; Scanner только читает результат
    (``10_LEVEL_1_SCANNER.md`` §46, §48). Неизвестный обязательный расход
    порог не проходит (``02_LEVEL1_SCANNER.md`` §32).
    """
    outcome = candidate.preliminary_result.threshold_outcome
    return outcome is not None and outcome.passed
