"""Resource Manager — единственная точка контроля внешних запросов.

Все внешние запросы проходят через него (``CLAUDE.md`` §14): Level 1,
Level 2, Fee System, Capability discovery, Telegram и maintenance не
обращаются к сети напрямую.

Он объединяет (``05_RESOURCE_MANAGER.md``, ``12_RESOURCE_MANAGER.md``):
приоритетную очередь, concurrency limits, rate limits, timeout, retry с
backoff и jitter, circuit breaker, дедупликацию, backpressure, отмену и
метрики задержек.
"""

from __future__ import annotations

import asyncio
import builtins
import random
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta

from monik.config.sections.resources import ResourceConfig
from monik.domain.enums.resources import CircuitState, ResourceResultStatus
from monik.domain.errors import MonikError, ResourceError, TimeoutError
from monik.domain.errors.base import ErrorInfo
from monik.domain.models.resource import ResourceKey, ResourceRequest, ResourceResult
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields
from monik.services.resources.circuit import CircuitBreaker
from monik.services.resources.dedup import InFlightRegistry
from monik.services.resources.gate import PriorityGate
from monik.services.resources.limits import RateLimiter, ResourceLimits
from monik.services.resources.retry import RetryPolicy

__all__ = ["ResourceManager", "Sleeper"]

_LOGGER = get_logger("services.resources")

#: Функция ожидания. Выделена, чтобы тесты управляли временем детерминированно.
Sleeper = Callable[[float], Awaitable[None]]

#: Ключ глобального лимита конкурентности.
_GLOBAL_GATE = "__global__"


class ResourceManager:
    """Выполняет внешние операции в рамках установленных ограничений."""

    def __init__(
        self,
        config: ResourceConfig,
        clock: Clock,
        *,
        limits: dict[str, ResourceLimits] | None = None,
        sleeper: Sleeper | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._limits = dict(limits or {})
        self._sleep: Sleeper = sleeper or asyncio.sleep
        self._retry = RetryPolicy(config.retry, rng=rng)
        self._gates: dict[str, PriorityGate] = {
            _GLOBAL_GATE: PriorityGate(
                limit=config.global_max_concurrent_requests,
                capacity=config.queue_capacity,
                name="global",
            )
        }
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._dedup = InFlightRegistry()
        self._results: list[ResourceResult] = []

    # --- публичный API -----------------------------------------------------

    async def execute[T](
        self, request: ResourceRequest, operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Выполнить операцию под контролем менеджера.

        Возвращает результат операции. Все ошибки нормализованы: наружу
        не выходят исключения библиотек.
        """
        if request.deduplication_key and self._config.deduplicate_in_flight:
            return await self._dedup.run(
                request.deduplication_key, lambda: self._execute_controlled(request, operation)
            )
        return await self._execute_controlled(request, operation)

    def register_limits(self, key: ResourceKey, limits: ResourceLimits) -> None:
        """Задать лимиты конкретного ресурса."""
        self._limits[str(key)] = limits

    def circuit_state(self, key: ResourceKey) -> CircuitState:
        """Состояние circuit breaker ресурса."""
        return self._breaker(str(key)).state

    def results(self) -> tuple[ResourceResult, ...]:
        """Метрики выполненных операций."""
        return tuple(self._results)

    @property
    def merged_requests(self) -> int:
        """Сколько запросов было объединено дедупликацией."""
        return self._dedup.merged_count

    def queue_depth(self) -> int:
        """Сколько запросов ожидает глобального разрешения."""
        return self._gates[_GLOBAL_GATE].waiting

    # --- выполнение --------------------------------------------------------

    async def _execute_controlled[T](
        self, request: ResourceRequest, operation: Callable[[], Awaitable[T]]
    ) -> T:
        resource = str(request.key)
        breaker = self._breaker(resource)
        if not breaker.allows_request():
            raise ResourceError(
                f"circuit breaker is open for {resource}",
                code="resource_circuit_open",
                request_id=request.request_id,
                operation=resource,
            )

        queue_started = time.monotonic()
        gates = self._gates_for(request.key)
        acquired: list[PriorityGate] = []
        try:
            for gate in gates:
                await gate.acquire(request, timeout=self._config.queue_wait_timeout_seconds)
                acquired.append(gate)
            queued_for = time.monotonic() - queue_started
            return await self._run_with_retry(request, operation, breaker, queued_for)
        finally:
            for gate in reversed(acquired):
                gate.release()

    async def _run_with_retry[T](
        self,
        request: ResourceRequest,
        operation: Callable[[], Awaitable[T]],
        breaker: CircuitBreaker,
        queued_for: float,
    ) -> T:
        attempts = 0
        started = time.monotonic()
        while True:
            await self._await_rate_limit(request)
            breaker.on_request_started()
            attempts += 1
            try:
                result = await asyncio.wait_for(
                    operation(), timeout=request.timeout.total_seconds()
                )
            except asyncio.CancelledError:
                self._record(request, ResourceResultStatus.CANCELLED, queued_for, started, attempts)
                raise
            except builtins.TimeoutError as exc:
                error = TimeoutError(
                    f"operation on {request.key} exceeded {request.timeout}",
                    code="resource_timeout",
                    request_id=request.request_id,
                    operation=str(request.key),
                )
                breaker.on_failure()
                if not self._retry.should_retry(error.info, attempts_used=attempts):
                    self._record(
                        request, ResourceResultStatus.TIMEOUT, queued_for, started, attempts
                    )
                    raise error from exc
                await self._backoff(request, error.info, attempts)
            except MonikError as error:
                if error.info.category.value == "cancellation":
                    self._record(
                        request, ResourceResultStatus.CANCELLED, queued_for, started, attempts
                    )
                    raise
                breaker.on_failure()
                if not self._retry.should_retry(error.info, attempts_used=attempts):
                    self._record(
                        request,
                        self._failure_status(error.info),
                        queued_for,
                        started,
                        attempts,
                        error=error.info,
                    )
                    raise
                await self._backoff(request, error.info, attempts)
            else:
                breaker.on_success()
                self._record(request, ResourceResultStatus.SUCCESS, queued_for, started, attempts)
                return result

    async def _await_rate_limit(self, request: ResourceRequest) -> None:
        """Дождаться разрешения rate limiter'а.

        Стоимость batch-запроса учитывается явно: несколько элементов не
        считаются одним запросом автоматически.
        """
        limiter = self._rate_limiter(request.key)
        if limiter is None:
            return
        while not limiter.try_consume(request.batch_units):
            delay = limiter.wait_time(request.batch_units)
            if delay <= 0:
                continue
            await self._sleep(delay)

    async def _backoff(self, request: ResourceRequest, error: ErrorInfo, attempts: int) -> None:
        """Выдержать паузу перед следующей попыткой.

        Экспонента отсчитывается от числа уже завершившихся попыток минус
        текущая: после первого сбоя задержка равна начальной.
        """
        delay = self._retry.delay_for(error, attempts_used=attempts - 1)
        _LOGGER.info(
            "retrying resource operation",
            extra=log_fields(
                resource=str(request.key),
                attempt=attempts,
                delay_seconds=round(delay, 3),
                error_code=error.code,
            ),
        )
        if delay > 0:
            await self._sleep(delay)

    # --- вспомогательное ---------------------------------------------------

    def _gates_for(self, key: ResourceKey) -> tuple[PriorityGate, ...]:
        """Ворота от самых широких к самым узким.

        Детерминированный порядок захвата предотвращает взаимную блокировку
        (``05_RESOURCE_MANAGER.md`` §44).
        """
        gates = [self._gates[_GLOBAL_GATE]]
        for scope in (*key.parents(), key):
            gates.append(self._gate(str(scope)))
        return tuple(gates)

    def _gate(self, name: str) -> PriorityGate:
        gate = self._gates.get(name)
        if gate is None:
            limits = self._limits.get(name)
            gate = PriorityGate(
                limit=limits.max_concurrent
                if limits
                else self._config.global_max_concurrent_requests,
                capacity=self._config.queue_capacity,
                name=name,
            )
            self._gates[name] = gate
        return gate

    def _rate_limiter(self, key: ResourceKey) -> RateLimiter | None:
        """Rate limiter самого узкого настроенного уровня."""
        for scope in (key, *reversed(key.parents())):
            name = str(scope)
            existing = self._rate_limiters.get(name)
            if existing is not None:
                return existing
            limits = self._limits.get(name)
            if limits is not None:
                limiter = RateLimiter(limits, self._clock)
                self._rate_limiters[name] = limiter
                return limiter
        return None

    def _breaker(self, name: str) -> CircuitBreaker:
        breaker = self._breakers.get(name)
        if breaker is None:
            breaker = CircuitBreaker(self._config.circuit_breaker, self._clock)
            self._breakers[name] = breaker
        return breaker

    @staticmethod
    def _failure_status(error: ErrorInfo) -> ResourceResultStatus:
        """Сопоставить категорию ошибки со статусом результата."""
        if error.category.value == "rate_limit":
            return ResourceResultStatus.RATE_LIMITED
        if error.category.value == "timeout":
            return ResourceResultStatus.TIMEOUT
        if error.category.value == "resource":
            return ResourceResultStatus.REJECTED
        return ResourceResultStatus.FAILURE

    def _record(
        self,
        request: ResourceRequest,
        status: ResourceResultStatus,
        queued_for: float,
        started: float,
        attempts: int,
        *,
        error: ErrorInfo | None = None,
    ) -> None:
        """Сохранить метрику выполнения."""
        self._results.append(
            ResourceResult(
                request_id=request.request_id,
                status=status,
                queued_for=timedelta(seconds=queued_for),
                executed_for=timedelta(seconds=time.monotonic() - started),
                attempts=attempts,
                finished_at=self._clock.now(),
                error_code=error.code if error else None,
                retry_after=error.retry_after if error else None,
            )
        )
