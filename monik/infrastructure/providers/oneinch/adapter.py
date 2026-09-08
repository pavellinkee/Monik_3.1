"""Adapter 1inch Classic Swap API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

Адаптер отвечает за построение запроса, разбор ответа, нормализацию
маршрута и комиссий и перевод ошибок; бизнес-решений он не принимает
(``06_AGGREGATOR_ADAPTERS.md`` §84).
"""

from __future__ import annotations

from typing import Any

from monik.config.secrets import SecretValue
from monik.config.sections.providers import ProviderConfig
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import RouteValidationOutcome, RoutingMode
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
    parse_optional_decimal,
    require_field,
)
from monik.infrastructure.providers.oneinch import endpoints
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["OneInchAdapter"]

_PROVIDER = ProviderId.ONEINCH

#: 1inch не раскрывает отдельный fixed-route режим: маршрут можно только
#: сравнить с полученным ответом (``06_AGGREGATOR_ADAPTERS.md`` §22, §51).
_SUPPORTS_FIXED_ROUTE = False


class OneInchAdapter(HttpProviderAdapter):
    """Реализация :class:`AggregatorAdapter` для 1inch."""

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
            supports_fee_discovery=False,
            supports_gas_estimate=True,
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Заявленные возможности адаптера."""
        return self._capabilities

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Получить котировку Classic Swap."""
        chain_id = self._require_chain_id(request.network_id)
        payload = await self.request_json(
            path=endpoints.quote_path(chain_id),
            network_id=request.network_id,
            operation=self._capability_operation(request),
            request_id=request.request_id,
            params=self._quote_params(request),
            priority=request.priority,
            correlation_id=request.correlation_id,
            timeout=request.timeout,
        )
        return self._to_quote(request, payload)

    async def validate_fixed_route(self, request: QuoteRequest) -> RouteValidation:
        """Проверить воспроизводимость зафиксированного маршрута.

        API не принимает маршрут как входной параметр, поэтому адаптер
        получает свежую котировку и **сравнивает** отпечатки. Молча принять
        другой маршрут нельзя (``06_AGGREGATOR_ADAPTERS.md`` §52).
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
            detail="1inch returned a different route for the same pair",
        )

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Подтвердить поддержку сети запросом списка токенов."""
        for name in endpoints.SUPPORTED_CHAIN_IDS:
            network_id = NetworkId(name)
            chain_id = endpoints.SUPPORTED_CHAIN_IDS[name]
            await self.request_json(
                path=endpoints.tokens_path(chain_id),
                network_id=network_id,
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=self._new_request_id(),
                deduplication_key=f"oneinch:tokens:{chain_id}",
            )
        return self._capabilities

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Комиссии 1inch не публикуются отдельным endpoint'ом.

        Возвращается пустой набор: выдумывать компоненты запрещено
        (``06_AGGREGATOR_ADAPTERS.md`` §39). Комиссия агрегатора, если она
        есть, отражается в ``dstAmount`` и учитывается Fee Policy.
        """
        return ()

    async def health_check(self) -> AdapterHealth:
        """Проверить доступность API списком источников ликвидности."""
        network_name = next(iter(endpoints.SUPPORTED_CHAIN_IDS))
        chain_id = endpoints.SUPPORTED_CHAIN_IDS[network_name]
        try:
            await self.request_json(
                path=endpoints.liquidity_sources_path(chain_id),
                network_id=NetworkId(network_name),
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=self._new_request_id(),
                deduplication_key=f"oneinch:health:{chain_id}",
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
    def _quote_params(request: QuoteRequest) -> dict[str, str]:
        """Параметры запроса котировки."""
        params = {
            "src": str(request.input_token.address),
            "dst": str(request.output_token.address),
            "amount": str(request.input_amount.raw),
            "includeProtocols": "true",
            "includeGas": "true",
        }
        if request.slippage_bps is not None:
            params["slippage"] = str(request.slippage_bps / 100)
        return params

    def _require_chain_id(self, network_id: NetworkId) -> int:
        chain_id = endpoints.chain_id_for(network_id)
        if chain_id is None:
            raise UnsupportedError(
                f"1inch adapter does not support network {network_id}",
                code="provider_network_unsupported",
                provider_code=_PROVIDER.value,
            )
        return chain_id

    @staticmethod
    def _capability_operation(request: QuoteRequest) -> CapabilityOperation:
        return (
            CapabilityOperation.QUOTE_BUY
            if request.operation.value == "buy"
            else CapabilityOperation.QUOTE_SELL
        )

    @staticmethod
    def _new_request_id() -> RequestId:
        """Идентификатор служебного запроса адаптера."""
        return RequestId.generate()

    # --- разбор ответа ----------------------------------------------------

    def _to_quote(self, request: QuoteRequest, payload: Any) -> Quote:
        """Преобразовать ответ API в нормализованную котировку."""
        if not isinstance(payload, dict):
            raise DataError(
                "1inch response is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        output_raw = parse_base_units(
            require_field(payload, "dstAmount", provider=_PROVIDER),
            provider=_PROVIDER,
            field="dstAmount",
        )
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
            price_impact=parse_optional_decimal(
                payload.get("priceImpact"), provider=_PROVIDER, field="priceImpact"
            ),
            slippage_bps=request.slippage_bps,
            provider_metadata=(("api_version", endpoints.API_VERSION),),
            # ``dstAmount`` — итоговая сумма маршрута. Комиссия агрегатора,
            # если она применяется, уже отражена в ней, поэтому повторно
            # вычитать её нельзя (``01_PROJECT_REQUIREMENTS.md`` §29).
            output_includes_fees=True,
        )

    def _to_route(self, request: QuoteRequest, payload: dict[str, Any]) -> Route:
        """Собрать нормализованный маршрут из поля ``protocols``."""
        protocols = payload.get("protocols")
        steps = self._parse_protocol_steps(request, protocols)
        return Route(
            provider_id=_PROVIDER,
            network_id=request.network_id,
            operation=request.operation,
            routing_mode=RoutingMode.CLASSIC,
            input_token=request.input_token.key,
            output_token=request.output_token.key,
            steps=steps,
            provider_parameters=(("api_version", endpoints.API_VERSION),),
        )

    def _parse_protocol_steps(self, request: QuoteRequest, protocols: Any) -> tuple[RouteStep, ...]:
        """Преобразовать вложенные списки протоколов в шаги маршрута.

        1inch описывает маршрут как список частей, каждая из которых —
        список параллельных источников ликвидности. Порядок протоколов
        внутри части нормализуется, чтобы отпечаток не зависел от порядка
        элементов в JSON (``06_AGGREGATOR_ADAPTERS.md`` §83).

        Если структура отсутствует, маршрут описывается одним шагом: шаги
        не выдумываются (``06_AGGREGATOR_ADAPTERS.md`` §39).
        """
        if not isinstance(protocols, list) or not protocols:
            return (
                RouteStep(
                    input_token=request.input_token.key,
                    output_token=request.output_token.key,
                    protocol="1inch_aggregate",
                ),
            )
        names: list[str] = []
        for part in protocols:
            names.extend(self._collect_protocol_names(part))
        if not names:
            return (
                RouteStep(
                    input_token=request.input_token.key,
                    output_token=request.output_token.key,
                    protocol="1inch_aggregate",
                ),
            )
        return (
            RouteStep(
                input_token=request.input_token.key,
                output_token=request.output_token.key,
                protocol="+".join(sorted(set(names))),
            ),
        )

    def _collect_protocol_names(self, node: Any) -> list[str]:
        """Рекурсивно собрать имена источников ликвидности."""
        if isinstance(node, dict):
            name = node.get("name")
            return [str(name)] if name else []
        if isinstance(node, list):
            collected: list[str] = []
            for item in node:
                collected.extend(self._collect_protocol_names(item))
            return collected
        return []
