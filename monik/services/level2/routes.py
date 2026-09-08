"""Проверка зафиксированного маршрута.

Маршрут Opportunity **immutable** для Level 2
(``11_LEVEL_2_SCANNER.md`` §5): нельзя заменить агрегатор, пул, путь или
routing mode. Если маршрут невозможно воспроизвести, альтернатива не
подбирается — результат ``ROUTE_UNAVAILABLE`` (§6, §51).

Provider-specific интерпретацию маршрута выполняет Adapter (§20). Level 2
дополнительно сверяет отпечаток ответа с отпечатком Opportunity (§18):
если соответствие подтвердить нельзя, маршрут считается неподтверждённым.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.operations import RouteValidationOutcome
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import MonikError
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route
from monik.domain.models.token import Token
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.identifiers import RequestId
from monik.infrastructure.providers.contract import AggregatorAdapter, QuoteRequest
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields
from monik.services.registries.capabilities import CapabilityRegistry

__all__ = ["RouteCheck", "RouteVerifier"]

_LOGGER = get_logger("services.level2.routes")


@dataclass(frozen=True, slots=True)
class RouteCheck:
    """Итог проверки одной ноги маршрута."""

    outcome: RouteValidationOutcome
    quote: Quote | None = None
    detail: str | None = None
    error: MonikError | None = None

    @property
    def is_reproduced(self) -> bool:
        """Воспроизведён ли исходный маршрут."""
        return self.outcome is RouteValidationOutcome.REPRODUCED and self.quote is not None


class RouteVerifier:
    """Получает свежую котировку строго по зафиксированному маршруту."""

    def __init__(
        self,
        adapters: dict[ProviderId, AggregatorAdapter],
        capabilities: CapabilityRegistry,
        clock: Clock,
        *,
        quote_max_age: timedelta,
        request_timeout: timedelta | None = None,
    ) -> None:
        self._adapters = adapters
        self._capabilities = capabilities
        self._clock = clock
        self._quote_max_age = quote_max_age
        self._request_timeout = request_timeout

    async def verify(
        self,
        route: Route,
        *,
        input_token: Token,
        output_token: Token,
        input_amount: TokenAmount,
    ) -> RouteCheck:
        """Проверить ногу маршрута и вернуть свежую котировку.

        Level 1 quote актуальным подтверждением не является (§12-13):
        запрашивается новая котировка.
        """
        adapter = self._adapters.get(route.provider_id)
        if adapter is None:
            return RouteCheck(
                outcome=RouteValidationOutcome.UNSUPPORTED,
                detail=f"adapter for {route.provider_id.value} is not configured",
            )
        blocked = self._capability_block(route)
        if blocked is not None:
            return RouteCheck(outcome=RouteValidationOutcome.UNSUPPORTED, detail=blocked)

        request = QuoteRequest(
            network_id=route.network_id,
            operation=route.operation,
            input_token=input_token,
            output_token=output_token,
            input_amount=input_amount,
            request_id=RequestId.generate(),
            routing_mode=route.routing_mode,
            fixed_route=route,
            priority=RequestPriority.LEVEL2,
            timeout=self._request_timeout,
        )
        try:
            validation = await adapter.validate_fixed_route(request)
        except MonikError as error:
            # Ошибка API не является признаком убыточности (§53, §55).
            _LOGGER.warning(
                "fixed route validation failed",
                extra=log_fields(
                    provider=route.provider_id.value,
                    operation=route.operation.value,
                    error_category=error.info.category.value,
                ),
            )
            return RouteCheck(
                outcome=RouteValidationOutcome.UNSUPPORTED,
                detail=error.info.message,
                error=error,
            )

        if not validation.is_reproduced or validation.quote is None:
            return RouteCheck(outcome=validation.outcome, detail=validation.detail)
        return self._check_quote(validation.quote, route, request)

    def _capability_block(self, route: Route) -> str | None:
        """Явно неподдерживаемый fixed route блокирует запрос (§22)."""
        key = self._capabilities.key(
            route.provider_id,
            route.network_id,
            CapabilityOperation.FIXED_ROUTE,
        )
        if self._capabilities.status(key) is CapabilityStatus.UNSUPPORTED:
            return f"{route.provider_id.value} does not support fixed-route verification"
        return None

    def _check_quote(self, quote: Quote, route: Route, request: QuoteRequest) -> RouteCheck:
        """Сверить котировку с зафиксированным маршрутом (§18-19)."""
        mismatch = _route_mismatch(quote, route)
        if mismatch is not None:
            return RouteCheck(outcome=RouteValidationOutcome.MISMATCH, detail=mismatch)
        if not quote.is_fresh(self._clock.now(), self._quote_max_age):
            return RouteCheck(
                outcome=RouteValidationOutcome.UNSUPPORTED,
                detail="verification quote is not fresh enough",
            )
        if not quote.has_usable_output:
            return RouteCheck(
                outcome=RouteValidationOutcome.UNSUPPORTED,
                detail="verification quote has zero output",
            )
        if quote.input_amount != request.input_amount:
            return RouteCheck(
                outcome=RouteValidationOutcome.MISMATCH,
                detail="verification quote does not describe the requested amount",
            )
        return RouteCheck(outcome=RouteValidationOutcome.REPRODUCED, quote=quote)


def _route_mismatch(quote: Quote, route: Route) -> str | None:
    """Причина несоответствия маршрута, либо ``None`` (§19)."""
    if quote.provider_id is not route.provider_id:
        return "verification quote uses a different aggregator"
    if quote.network_id != route.network_id:
        return "verification quote belongs to a different network"
    if quote.operation is not route.operation:
        return "verification quote describes a different operation"
    if quote.input_token != route.input_token:
        return "verification quote input token differs from the fixed route"
    if quote.output_token != route.output_token:
        return "verification quote output token differs from the fixed route"
    if quote.route.routing_mode is not route.routing_mode:
        return "verification quote uses a different routing mode"
    if quote.route.fingerprint != route.fingerprint:
        return "verification quote route fingerprint differs from the fixed route"
    return None
