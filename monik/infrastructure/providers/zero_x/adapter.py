"""Adapter 0x Swap API v2.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

0x возвращает состав маршрута в поле ``route.fills``, поэтому адаптер может
восстановить источники ликвидности и их доли и построить детерминированный
отпечаток маршрута.
"""

from __future__ import annotations

from typing import Any

from monik.config.secrets import SecretValue
from monik.config.sections.providers import ProviderConfig
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import (
    OperationType,
    RouteValidationOutcome,
    RoutingMode,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DataError, MonikError, UnsupportedError
from monik.domain.models.fee import Fee
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route, RouteStep
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.http import HttpClient
from monik.infrastructure.providers.contract import (
    AdapterCapabilities,
    AdapterHealth,
    QuoteRequest,
    RouteValidation,
)
from monik.infrastructure.providers.http_adapter import HttpProviderAdapter
from monik.infrastructure.providers.normalization import (
    build_quote,
    parse_base_units,
    require_field,
)
from monik.infrastructure.providers.zero_x import endpoints
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["ZeroXAdapter"]

_PROVIDER = ProviderId.ZERO_X

#: API не принимает готовый маршрут как входной параметр, поэтому
#: воспроизведение проверяется сравнением отпечатков
#: (``06_AGGREGATOR_ADAPTERS.md`` §22, §51).
_SUPPORTS_FIXED_ROUTE = False


class ZeroXAdapter(HttpProviderAdapter):
    """Реализация :class:`AggregatorAdapter` для 0x."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        api_key: SecretValue | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            _PROVIDER,
            config,
            http=http,
            resources=resources,
            clock=clock,
            api_key=api_key,
            base_url=base_url or config.base_url or endpoints.DEFAULT_BASE_URL,
        )
        self._capabilities = AdapterCapabilities(
            provider_id=_PROVIDER,
            supported_networks=frozenset(NetworkId(name) for name in endpoints.SUPPORTED_CHAIN_IDS),
            routing_modes=frozenset({RoutingMode.CLASSIC}),
            supports_fixed_route=_SUPPORTS_FIXED_ROUTE,
            supports_fee_discovery=True,
            supports_gas_estimate=True,
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Заявленные возможности адаптера."""
        return self._capabilities

    def auth_headers(self) -> dict[str, str]:
        """Заголовки 0x: ключ доступа и версия API.

        Схема аутентификации отличается от Bearer, поэтому базовая
        реализация переопределяется здесь, внутри адаптера
        (``06_AGGREGATOR_ADAPTERS.md`` §14).
        """
        headers = {endpoints.API_VERSION_HEADER: endpoints.API_VERSION}
        if self._api_key is not None:
            headers[endpoints.API_KEY_HEADER] = self._api_key.get()
        return headers

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Получить индикативную цену."""
        chain_id = self._require_chain_id(request.network_id)
        payload = await self.request_json(
            path=endpoints.PRICE_PATH,
            network_id=request.network_id,
            operation=self._capability_operation(request),
            request_id=request.request_id,
            params=self._price_params(request, chain_id),
            priority=request.priority,
            correlation_id=request.correlation_id,
            timeout=request.timeout,
        )
        return self._to_quote(request, payload)

    async def validate_fixed_route(self, request: QuoteRequest) -> RouteValidation:
        """Сравнить свежий маршрут с зафиксированным Level 1."""
        if request.fixed_route is None:
            raise DataError(
                "fixed route validation requires the route fixed by Level 1",
                code="fixed_route_missing",
                provider_code=_PROVIDER.value,
            )
        quote = await self.get_quote(request)
        observed = quote.route.fingerprint
        if observed == request.fixed_route.fingerprint:
            return RouteValidation(
                outcome=RouteValidationOutcome.REPRODUCED,
                quote=quote,
                observed_fingerprint=observed,
            )
        return RouteValidation(
            outcome=RouteValidationOutcome.MISMATCH,
            observed_fingerprint=observed,
            detail="0x returned a different set of fills for the same pair",
        )

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Подтвердить доступность API списком источников ликвидности."""
        for name, chain_id in endpoints.SUPPORTED_CHAIN_IDS.items():
            await self.request_json(
                path=endpoints.SOURCES_PATH,
                network_id=NetworkId(name),
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=RequestId.generate(),
                params={"chainId": str(chain_id)},
                deduplication_key=f"zero_x:sources:{chain_id}",
            )
        return self._capabilities

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Комиссии 0x возвращаются вместе с ценой, а не отдельно.

        Отдельного endpoint'а нет, поэтому здесь набор пуст: выдумывать
        компоненты запрещено (``06_AGGREGATOR_ADAPTERS.md`` §39).
        """
        return ()

    async def health_check(self) -> AdapterHealth:
        """Проверить доступность API."""
        name, chain_id = next(iter(endpoints.SUPPORTED_CHAIN_IDS.items()))
        try:
            await self.request_json(
                path=endpoints.SOURCES_PATH,
                network_id=NetworkId(name),
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=RequestId.generate(),
                params={"chainId": str(chain_id)},
                deduplication_key=f"zero_x:health:{chain_id}",
            )
        except MonikError as error:
            return AdapterHealth(
                provider_id=_PROVIDER,
                state=AdapterState.DEGRADED,
                detail=error.info.code,
            )
        return AdapterHealth(provider_id=_PROVIDER, state=AdapterState.READY)

    # --- построение запроса ----------------------------------------------

    @staticmethod
    def _price_params(request: QuoteRequest, chain_id: int) -> dict[str, str]:
        """Параметры индикативной цены."""
        params = {
            "chainId": str(chain_id),
            "sellToken": str(request.input_token.address),
            "buyToken": str(request.output_token.address),
            "sellAmount": str(request.input_amount.raw),
        }
        if request.slippage_bps is not None:
            params["slippageBps"] = str(request.slippage_bps)
        return params

    def _require_chain_id(self, network_id: NetworkId) -> int:
        chain_id = endpoints.chain_id_for(network_id)
        if chain_id is None:
            raise UnsupportedError(
                f"0x adapter does not support network {network_id}",
                code="provider_network_unsupported",
                provider_code=_PROVIDER.value,
            )
        return chain_id

    @staticmethod
    def _capability_operation(request: QuoteRequest) -> CapabilityOperation:
        return (
            CapabilityOperation.QUOTE_BUY
            if request.operation is OperationType.BUY
            else CapabilityOperation.QUOTE_SELL
        )

    # --- разбор ответа ----------------------------------------------------

    def _to_quote(self, request: QuoteRequest, payload: Any) -> Quote:
        """Преобразовать ответ в нормализованную котировку."""
        if not isinstance(payload, dict):
            raise DataError(
                "0x response is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        output_raw = parse_base_units(
            require_field(payload, "buyAmount", provider=_PROVIDER),
            provider=_PROVIDER,
            field="buyAmount",
        )
        self._verify_sell_amount(request, payload)
        gas = payload.get("gas")
        gas_units = (
            parse_base_units(gas, provider=_PROVIDER, field="gas") if gas is not None else None
        )
        return build_quote(
            provider_id=_PROVIDER,
            request=request,
            output_raw=output_raw,
            route=self._to_route(request, payload),
            created_at=self._clock.now(),
            estimated_gas_units=gas_units,
            slippage_bps=request.slippage_bps,
            provider_metadata=(("api_version", endpoints.API_VERSION),),
            # ``buyAmount`` уже учитывает комиссии маршрута, поэтому
            # повторно вычитать их нельзя (``01_PROJECT_REQUIREMENTS.md`` §29).
            output_includes_fees=True,
        )

    @staticmethod
    def _verify_sell_amount(request: QuoteRequest, payload: dict[str, Any]) -> None:
        """Убедиться, что ответ относится к запрошенной сумме.

        Несовпадение суммы делает ответ невалидным
        (``06_AGGREGATOR_ADAPTERS.md`` §37).
        """
        raw = payload.get("sellAmount")
        if raw is None:
            return
        actual = parse_base_units(raw, provider=_PROVIDER, field="sellAmount")
        if actual != request.input_amount.raw:
            raise DataError(
                "0x returned a quote for a different sell amount",
                code="provider_amount_mismatch",
                provider_code=_PROVIDER.value,
            )

    def _to_route(self, request: QuoteRequest, payload: dict[str, Any]) -> Route:
        """Собрать маршрут из ``route.fills``."""
        return Route(
            provider_id=_PROVIDER,
            network_id=request.network_id,
            operation=request.operation,
            routing_mode=RoutingMode.CLASSIC,
            input_token=request.input_token.key,
            output_token=request.output_token.key,
            steps=self._parse_fills(request, payload.get("route")),
            provider_parameters=(("api_version", endpoints.API_VERSION),),
        )

    def _parse_fills(self, request: QuoteRequest, route: Any) -> tuple[RouteStep, ...]:
        """Преобразовать ``fills`` в нормализованные шаги.

        Порядок источников нормализуется, поэтому отпечаток не зависит от
        порядка элементов в ответе (``06_AGGREGATOR_ADAPTERS.md`` §83).
        Если состав маршрута не раскрыт, создаётся один шаг: выдумывать
        промежуточные пулы запрещено (§39).
        """
        fills = route.get("fills") if isinstance(route, dict) else None
        sources: list[str] = []
        if isinstance(fills, list):
            for fill in fills:
                if isinstance(fill, dict) and fill.get("source"):
                    sources.append(str(fill["source"]))
        protocol = "+".join(sorted(set(sources))) if sources else "0x_aggregate"
        return (
            RouteStep(
                input_token=request.input_token.key,
                output_token=request.output_token.key,
                protocol=protocol,
            ),
        )
