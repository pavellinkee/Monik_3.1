"""Детерминированный адаптер для тестов.

**Test implementation, не production** (``CLAUDE.md`` §10, §46).
Используется в component-, integration- и E2E-тестах, чтобы проверять
workflow без обращения к внешним API (``23_TESTING.md`` §12).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import RouteValidationOutcome, RoutingMode
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import MonikError
from monik.domain.models.fee import Fee
from monik.domain.models.quote import Quote
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.providers.contract import (
    AdapterCapabilities,
    AdapterHealth,
    QuoteRequest,
    RouteValidation,
)
from monik.infrastructure.providers.normalization import build_quote, build_single_step_route
from monik.services.observability.clock import Clock

__all__ = ["FakeAdapter"]

#: Функция, вычисляющая output в base units по запросу.
OutputRule = Callable[[QuoteRequest], int]


class FakeAdapter:
    """Адаптер с предсказуемым поведением.

    Позволяет задать курс обмена, ошибки, поведение fixed-route и состояние
    здоровья, не выполняя сетевых вызовов.
    """

    def __init__(
        self,
        provider_id: ProviderId,
        clock: Clock,
        *,
        rate: Decimal = Decimal("1"),
        output_rule: OutputRule | None = None,
        capabilities: AdapterCapabilities | None = None,
        error: MonikError | None = None,
        fixed_route_outcome: RouteValidationOutcome = RouteValidationOutcome.REPRODUCED,
        fees: tuple[Fee, ...] | None = None,
        state: AdapterState = AdapterState.READY,
    ) -> None:
        self._provider_id = provider_id
        self._clock = clock
        self._rate = rate
        self._output_rule = output_rule
        self._capabilities = capabilities or AdapterCapabilities(
            provider_id=provider_id,
            supported_networks=frozenset({NetworkId("polygon")}),
            routing_modes=frozenset({RoutingMode.CLASSIC}),
            supports_fixed_route=True,
            supports_fee_discovery=True,
            supports_gas_estimate=True,
        )
        self._error = error
        self._fixed_route_outcome = fixed_route_outcome
        self._fees = fees
        self._state = state
        self.quote_calls: list[QuoteRequest] = []
        self.closed = False

    @property
    def provider_id(self) -> ProviderId:
        """Идентификатор провайдера."""
        return self._provider_id

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Заданные возможности адаптера."""
        return self._capabilities

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Вернуть детерминированную котировку."""
        self.quote_calls.append(request)
        if self._error is not None:
            raise self._error
        return build_quote(
            provider_id=self._provider_id,
            request=request,
            output_raw=self._output_for(request),
            route=build_single_step_route(
                provider_id=self._provider_id,
                request=request,
                routing_mode=request.routing_mode or RoutingMode.CLASSIC,
                protocol="fake_pool",
            ),
            created_at=self._clock.now(),
            estimated_gas_units=200_000,
        )

    async def validate_fixed_route(self, request: QuoteRequest) -> RouteValidation:
        """Проверить зафиксированный маршрут согласно настройке."""
        if self._fixed_route_outcome is RouteValidationOutcome.UNSUPPORTED:
            return RouteValidation(
                outcome=RouteValidationOutcome.UNSUPPORTED,
                detail="fake adapter configured without fixed-route support",
            )
        quote = await self.get_quote(request)
        if self._fixed_route_outcome is RouteValidationOutcome.MISMATCH:
            return RouteValidation(
                outcome=RouteValidationOutcome.MISMATCH,
                observed_fingerprint=quote.route.fingerprint,
                detail="fake adapter configured to report a different route",
            )
        return RouteValidation(
            outcome=RouteValidationOutcome.REPRODUCED,
            quote=quote,
            observed_fingerprint=quote.route.fingerprint,
        )

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Вернуть заданные возможности."""
        return self._capabilities

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Вернуть заданные комиссии.

        По умолчанию набор пуст: fake-адаптер не выдумывает компоненты,
        которых не знает (``06_AGGREGATOR_ADAPTERS.md`` §39). Тест,
        которому нужны комиссии, задаёт их явно.
        """
        return self._fees if self._fees is not None else ()

    async def health_check(self) -> AdapterHealth:
        """Вернуть заданное состояние."""
        return AdapterHealth(provider_id=self._provider_id, state=self._state)

    async def aclose(self) -> None:
        """Отметить адаптер закрытым."""
        self.closed = True

    def _output_for(self, request: QuoteRequest) -> int:
        if self._output_rule is not None:
            return self._output_rule(request)
        human = request.input_amount.as_decimal * self._rate
        scaled = human.scaleb(request.output_token.decimals)
        return int(scaled)
