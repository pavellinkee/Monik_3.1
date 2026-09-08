"""Adapter Uniswap Trading API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

Ключевая особенность: Uniswap различает Classic и семейство UniswapX.
Эти режимы **не объединяются** — routing mode является частью identity
маршрута (``06_AGGREGATOR_ADAPTERS.md`` §26-27), поэтому маршрут, полученный
в другом режиме, не считается тем же самым маршрутом.
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
from monik.infrastructure.providers.uniswap import endpoints
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["UniswapAdapter"]

_PROVIDER = ProviderId.UNISWAP

#: Trading API позволяет задать предпочтение маршрутизации, но не принимает
#: конкретный маршрут как входной параметр, поэтому воспроизведение
#: проверяется сравнением отпечатков (``06_AGGREGATOR_ADAPTERS.md`` §51).
_SUPPORTS_FIXED_ROUTE = False


class UniswapAdapter(HttpProviderAdapter):
    """Реализация :class:`AggregatorAdapter` для Uniswap."""

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
            routing_modes=frozenset(endpoints.ROUTING_MODES.values()),
            supports_fixed_route=_SUPPORTS_FIXED_ROUTE,
            supports_fee_discovery=False,
            supports_gas_estimate=True,
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Заявленные возможности адаптера."""
        return self._capabilities

    def auth_headers(self) -> dict[str, str]:
        """Заголовок с ключом Trading API."""
        if self._api_key is None:
            return {}
        return {endpoints.API_KEY_HEADER: self._api_key.get()}

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Получить котировку Trading API."""
        chain_id = self._require_chain_id(request.network_id)
        payload = await self.request_json(
            path=endpoints.QUOTE_PATH,
            network_id=request.network_id,
            operation=self._capability_operation(request),
            request_id=request.request_id,
            method="POST",
            json_body=self._quote_body(request, chain_id),
            priority=request.priority,
            correlation_id=request.correlation_id,
            timeout=request.timeout,
        )
        return self._to_quote(request, payload)

    async def validate_fixed_route(self, request: QuoteRequest) -> RouteValidation:
        """Сравнить свежий маршрут с зафиксированным Level 1.

        Запрос выполняется в том же routing mode, в котором был найден
        исходный маршрут: подмена режима недопустима.
        """
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
            detail="uniswap returned a different route or routing mode",
        )

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Возможности заданы контрактом API и не уточняются запросом.

        Отдельного endpoint'а описания возможностей нет, поэтому набор
        не выдумывается.
        """
        return self._capabilities

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Отдельного endpoint'а комиссий нет."""
        return ()

    async def health_check(self) -> AdapterHealth:
        """Проверить доступность API минимальным запросом котировки."""
        name, chain_id = next(iter(endpoints.SUPPORTED_CHAIN_IDS.items()))
        try:
            await self.request_json(
                path=endpoints.QUOTE_PATH,
                network_id=NetworkId(name),
                operation=CapabilityOperation.QUOTE_BUY,
                request_id=RequestId.generate(),
                method="POST",
                json_body={"type": "EXACT_INPUT", "tokenInChainId": chain_id},
                deduplication_key=f"uniswap:health:{chain_id}",
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
    def _quote_body(request: QuoteRequest, chain_id: int) -> dict[str, Any]:
        """Тело POST-запроса котировки."""
        body: dict[str, Any] = {
            "type": "EXACT_INPUT",
            "amount": str(request.input_amount.raw),
            "tokenInChainId": chain_id,
            "tokenOutChainId": chain_id,
            "tokenIn": str(request.input_token.address),
            "tokenOut": str(request.output_token.address),
            "routingPreference": endpoints.routing_preference_for(request.routing_mode),
        }
        if request.slippage_bps is not None:
            body["slippageTolerance"] = request.slippage_bps / 100
        return body

    def _require_chain_id(self, network_id: NetworkId) -> int:
        chain_id = endpoints.chain_id_for(network_id)
        if chain_id is None:
            raise UnsupportedError(
                f"uniswap adapter does not support network {network_id}",
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
        """Преобразовать ответ Trading API в нормализованную котировку."""
        if not isinstance(payload, dict):
            raise DataError(
                "uniswap response is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        routing_mode = self._routing_mode(payload)
        quote_body = require_field(payload, "quote", provider=_PROVIDER)
        if not isinstance(quote_body, dict):
            raise DataError(
                "uniswap quote is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        output_raw = self._output_amount(quote_body)
        gas = quote_body.get("gasUseEstimate")
        gas_units = (
            parse_base_units(gas, provider=_PROVIDER, field="gasUseEstimate")
            if gas is not None
            else None
        )
        return build_quote(
            provider_id=_PROVIDER,
            request=request,
            output_raw=output_raw,
            route=self._to_route(request, quote_body, routing_mode),
            created_at=self._clock.now(),
            estimated_gas_units=gas_units,
            slippage_bps=request.slippage_bps,
            provider_metadata=(("routing", routing_mode.value),),
            output_includes_fees=True,
        )

    @staticmethod
    def _routing_mode(payload: dict[str, Any]) -> RoutingMode:
        """Определить routing mode ответа.

        Неизвестное значение не подменяется существующим режимом: фиктивные
        режимы создавать запрещено (``06_AGGREGATOR_ADAPTERS.md`` §26).
        """
        raw = require_field(payload, "routing", provider=_PROVIDER)
        mode = endpoints.routing_mode_for(str(raw))
        if mode is None:
            raise DataError(
                f"uniswap returned an unknown routing mode: {raw!r}",
                code="provider_routing_mode_unknown",
                provider_code=_PROVIDER.value,
            )
        return mode

    @staticmethod
    def _output_amount(quote_body: dict[str, Any]) -> int:
        """Извлечь итоговую сумму из ответа."""
        output = quote_body.get("output")
        if isinstance(output, dict) and output.get("amount") is not None:
            return parse_base_units(output["amount"], provider=_PROVIDER, field="output.amount")
        return parse_base_units(
            require_field(quote_body, "quote", provider=_PROVIDER),
            provider=_PROVIDER,
            field="quote",
        )

    def _to_route(
        self, request: QuoteRequest, quote_body: dict[str, Any], routing_mode: RoutingMode
    ) -> Route:
        """Собрать маршрут с сохранением routing mode."""
        return Route(
            provider_id=_PROVIDER,
            network_id=request.network_id,
            operation=request.operation,
            routing_mode=routing_mode,
            input_token=request.input_token.key,
            output_token=request.output_token.key,
            steps=self._parse_route_steps(request, quote_body.get("route")),
            provider_parameters=(("routing", routing_mode.value),),
        )

    def _parse_route_steps(self, request: QuoteRequest, route: Any) -> tuple[RouteStep, ...]:
        """Собрать шаги маршрута из ответа Classic-маршрутизации.

        Порядок пулов нормализуется, поэтому отпечаток устойчив
        (``06_AGGREGATOR_ADAPTERS.md`` §83). Для UniswapX состав пулов не
        раскрывается — в этом случае создаётся один шаг, а не выдуманная
        цепочка (§39).
        """
        pools = sorted(set(self._collect_pools(route)))
        protocol = "+".join(pools) if pools else "uniswap_aggregate"
        return (
            RouteStep(
                input_token=request.input_token.key,
                output_token=request.output_token.key,
                protocol=protocol,
            ),
        )

    def _collect_pools(self, node: Any) -> list[str]:
        """Рекурсивно собрать описания пулов маршрута."""
        if isinstance(node, dict):
            found: list[str] = []
            pool_type = node.get("type")
            address = node.get("address")
            if pool_type and address:
                found.append(f"{pool_type}:{address}")
            elif pool_type:
                found.append(str(pool_type))
            for value in node.values():
                if isinstance(value, list | dict):
                    found.extend(self._collect_pools(value))
            return found
        if isinstance(node, list):
            collected: list[str] = []
            for item in node:
                collected.extend(self._collect_pools(item))
            return collected
        return []
