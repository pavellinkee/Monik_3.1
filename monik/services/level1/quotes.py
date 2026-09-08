"""Получение и валидация котировок Level 1.

Все внешние запросы выполняются через Adapter, а тот — через Resource
Manager (``02_LEVEL1_SCANNER.md`` §11, ``10_LEVEL_1_SCANNER.md`` §17).
Scanner не выполняет HTTP-запросов сам и не знает деталей API провайдера.

Количество одновременных запросов ограничено: бесконечное число
asynchronous tasks запрещено (``02_LEVEL1_SCANNER.md`` §60).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from monik.domain.enums.errors import ErrorCategory
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import MonikError
from monik.domain.models.quote import Quote
from monik.domain.models.token import Token
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.identifiers import RequestId, ScanId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.providers.contract import AggregatorAdapter, QuoteRequest
from monik.services.level1.validation import quote_rejection_reason
from monik.services.observability.clock import Clock
from monik.services.observability.context import log_context
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["QuoteAttempt", "QuoteCollector", "QuoteStatistics"]

_LOGGER = get_logger("services.level1.quotes")

#: Приоритет запроса по направлению. Готовая SELL-проверка обслуживается
#: раньше незавершённой BUY-проверки (``CLAUDE.md`` §15).
_PRIORITIES: dict[OperationType, RequestPriority] = {
    OperationType.BUY: RequestPriority.LEVEL1_BUY,
    OperationType.SELL: RequestPriority.LEVEL1_SELL,
}


@dataclass(frozen=True, slots=True)
class QuoteAttempt:
    """Итог одной попытки получить котировку.

    Ошибка одного провайдера не останавливает цикл
    (``02_LEVEL1_SCANNER.md`` §51): она сохраняется здесь и учитывается
    в статистике.
    """

    provider_id: ProviderId
    operation: OperationType
    quote: Quote | None = None
    rejection_reason: str | None = None
    error_category: ErrorCategory | None = None
    error_message: str | None = None

    @property
    def is_usable(self) -> bool:
        """Можно ли использовать котировку в сравнении."""
        return self.quote is not None and self.rejection_reason is None


@dataclass(slots=True)
class QuoteStatistics:
    """Счётчики запросов одного цикла."""

    requests: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    attempts: list[QuoteAttempt] = field(default_factory=list)


class QuoteCollector:
    """Запрашивает котировки у адаптеров с ограниченной конкурентностью."""

    def __init__(
        self,
        adapters: dict[ProviderId, AggregatorAdapter],
        clock: Clock,
        *,
        scan_id: ScanId,
        max_age: timedelta,
        max_concurrent: int,
        request_timeout: timedelta | None = None,
    ) -> None:
        self._adapters = adapters
        self._clock = clock
        self._scan_id = scan_id
        self._max_age = max_age
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._request_timeout = request_timeout
        self.statistics = QuoteStatistics()

    async def fetch(
        self,
        provider_id: ProviderId,
        *,
        network_id: NetworkId,
        operation: OperationType,
        input_token: Token,
        output_token: Token,
        input_amount: TokenAmount,
    ) -> QuoteAttempt:
        """Получить и проверить одну котировку."""
        adapter = self._adapters[provider_id]
        request = QuoteRequest(
            network_id=network_id,
            operation=operation,
            input_token=input_token,
            output_token=output_token,
            input_amount=input_amount,
            request_id=RequestId.generate(),
            priority=_PRIORITIES[operation],
            timeout=self._request_timeout,
        )
        with log_context(
            scan_id=str(self._scan_id),
            request_id=str(request.request_id),
            provider=provider_id.value,
            network=str(network_id),
            operation=operation.value,
        ):
            return await self._fetch(adapter, request)

    def record_skipped(self, count: int = 1) -> None:
        """Учесть комбинацию, для которой запрос не выполнялся (§89)."""
        self.statistics.skipped += count

    async def _fetch(self, adapter: AggregatorAdapter, request: QuoteRequest) -> QuoteAttempt:
        self.statistics.requests += 1
        async with self._semaphore:
            try:
                quote = await adapter.get_quote(request)
            except MonikError as error:
                self.statistics.failed += 1
                attempt = QuoteAttempt(
                    provider_id=adapter.provider_id,
                    operation=request.operation,
                    error_category=error.info.category,
                    error_message=error.info.message,
                )
                self.statistics.attempts.append(attempt)
                _LOGGER.warning(
                    "quote request failed",
                    extra=log_fields(
                        error_category=error.info.category.value,
                        error_code=error.info.code,
                    ),
                )
                return attempt

        reason = quote_rejection_reason(
            quote,
            request,
            provider_id=adapter.provider_id,
            now=self._clock.now(),
            max_age=self._max_age,
        )
        if reason is not None:
            self.statistics.failed += 1
            attempt = QuoteAttempt(
                provider_id=adapter.provider_id,
                operation=request.operation,
                quote=quote,
                rejection_reason=reason,
            )
            self.statistics.attempts.append(attempt)
            _LOGGER.info("quote rejected", extra=log_fields(reason=reason))
            return attempt

        self.statistics.successful += 1
        attempt = QuoteAttempt(
            provider_id=adapter.provider_id,
            operation=request.operation,
            quote=quote,
        )
        self.statistics.attempts.append(attempt)
        return attempt
