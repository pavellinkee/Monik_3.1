"""Adapter Velora (ParaSwap) Market API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).

Velora использует двухшаговую модель ``/prices`` → ``/transactions``.
Monik не исполняет свопы (``01_PROJECT_REQUIREMENTS.md`` §55), поэтому
адаптер использует только ``/prices`` и нормализует ``priceRoute``.
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
from monik.infrastructure.providers.velora import endpoints
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["VeloraAdapter"]

_PROVIDER = ProviderId.VELORA

#: ``priceRoute`` возвращается ответом и передаётся в ``/transactions``
#: как есть. Для проверки Level 2 адаптер сравнивает отпечатки маршрута:
#: подставлять другой маршрут запрещено (``06_AGGREGATOR_ADAPTERS.md`` §52).
_SUPPORTS_FIXED_ROUTE = False


class VeloraAdapter(HttpProviderAdapter):
    """Реализация :class:`AggregatorAdapter` для Velora."""

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
            supported_networks=frozenset(
                NetworkId(name) for name in endpoints.SUPPORTED_NETWORK_IDS
            ),
            routing_modes=frozenset({RoutingMode.CLASSIC}),
            supports_fixed_route=_SUPPORTS_FIXED_ROUTE,
            supports_fee_discovery=False,
            supports_gas_estimate=True,
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Заявленные возможности адаптера."""
        return self._capabilities

    def auth_headers(self) -> dict[str, str]:
        """Заголовки Velora.

        Market API не требует ключа для получения котировок; partner-ключ,
        если он задан, передаётся отдельным заголовком.
        """
        if self._api_key is None:
            return {}
        return {"X-Partner": self._api_key.get()}

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Получить котировку из ``/prices``."""
        network = self._require_network(request.network_id)
        payload = await self.request_json(
            path=endpoints.PRICES_PATH,
            network_id=request.network_id,
            operation=self._capability_operation(request),
            request_id=request.request_id,
            params=self._price_params(request, network),
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
            detail="velora returned a different priceRoute for the same pair",
        )

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Подтвердить доступность API списком токенов сети."""
        for name, network in endpoints.SUPPORTED_NETWORK_IDS.items():
            await self.request_json(
                path=endpoints.tokens_path(network),
                network_id=NetworkId(name),
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=RequestId.generate(),
                deduplication_key=f"velora:tokens:{network}",
            )
        return self._capabilities

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Отдельного endpoint'а комиссий нет.

        Компоненты не выдумываются (``06_AGGREGATOR_ADAPTERS.md`` §39):
        стоимость маршрута отражена в ``destAmount``.
        """
        return ()

    async def health_check(self) -> AdapterHealth:
        """Проверить доступность API."""
        name, network = next(iter(endpoints.SUPPORTED_NETWORK_IDS.items()))
        try:
            await self.request_json(
                path=endpoints.tokens_path(network),
                network_id=NetworkId(name),
                operation=CapabilityOperation.TOKEN_METADATA,
                request_id=RequestId.generate(),
                deduplication_key=f"velora:health:{network}",
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
    def _price_params(request: QuoteRequest, network: int) -> dict[str, str]:
        """Параметры запроса котировки.

        ``srcDecimals``/``destDecimals`` берутся из Token Registry
        (``09_PROFIT_CALCULATOR.md`` §5), а не выводятся из символа.
        """
        return {
            "srcToken": str(request.input_token.address),
            "destToken": str(request.output_token.address),
            "srcDecimals": str(request.input_token.decimals),
            "destDecimals": str(request.output_token.decimals),
            "amount": str(request.input_amount.raw),
            "side": "SELL",
            "network": str(network),
            "version": endpoints.API_VERSION,
        }

    def _require_network(self, network_id: NetworkId) -> int:
        network = endpoints.network_id_for(network_id)
        if network is None:
            raise UnsupportedError(
                f"velora adapter does not support network {network_id}",
                code="provider_network_unsupported",
                provider_code=_PROVIDER.value,
            )
        return network

    @staticmethod
    def _capability_operation(request: QuoteRequest) -> CapabilityOperation:
        return (
            CapabilityOperation.QUOTE_BUY
            if request.operation is OperationType.BUY
            else CapabilityOperation.QUOTE_SELL
        )

    # --- разбор ответа ----------------------------------------------------

    def _to_quote(self, request: QuoteRequest, payload: Any) -> Quote:
        """Преобразовать ``priceRoute`` в нормализованную котировку."""
        if not isinstance(payload, dict):
            raise DataError(
                "velora response is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        price_route = require_field(payload, "priceRoute", provider=_PROVIDER)
        if not isinstance(price_route, dict):
            raise DataError(
                "velora priceRoute is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        output_raw = parse_base_units(
            require_field(price_route, "destAmount", provider=_PROVIDER),
            provider=_PROVIDER,
            field="destAmount",
        )
        self._verify_src_amount(request, price_route)
        gas = price_route.get("gasCost")
        gas_units = (
            parse_base_units(gas, provider=_PROVIDER, field="gasCost") if gas is not None else None
        )
        return build_quote(
            provider_id=_PROVIDER,
            request=request,
            output_raw=output_raw,
            route=self._to_route(request, price_route),
            created_at=self._clock.now(),
            estimated_gas_units=gas_units,
            slippage_bps=request.slippage_bps,
            provider_metadata=(("api_version", endpoints.API_VERSION),),
            # ``destAmount`` — итог маршрута с учётом его издержек.
            output_includes_fees=True,
        )

    @staticmethod
    def _verify_src_amount(request: QuoteRequest, price_route: dict[str, Any]) -> None:
        """Убедиться, что котировка относится к запрошенной сумме."""
        raw = price_route.get("srcAmount")
        if raw is None:
            return
        actual = parse_base_units(raw, provider=_PROVIDER, field="srcAmount")
        if actual != request.input_amount.raw:
            raise DataError(
                "velora returned a quote for a different source amount",
                code="provider_amount_mismatch",
                provider_code=_PROVIDER.value,
            )

    def _to_route(self, request: QuoteRequest, price_route: dict[str, Any]) -> Route:
        """Собрать маршрут из ``bestRoute``."""
        return Route(
            provider_id=_PROVIDER,
            network_id=request.network_id,
            operation=request.operation,
            routing_mode=RoutingMode.CLASSIC,
            input_token=request.input_token.key,
            output_token=request.output_token.key,
            steps=self._parse_best_route(request, price_route.get("bestRoute")),
            provider_parameters=(("api_version", endpoints.API_VERSION),),
        )

    def _parse_best_route(self, request: QuoteRequest, best_route: Any) -> tuple[RouteStep, ...]:
        """Извлечь названия обменников из вложенной структуры ``bestRoute``.

        Velora описывает маршрут списком percent-разбиений со вложенными
        ``swaps`` и ``swapExchanges``. Названия нормализуются и сортируются,
        поэтому отпечаток не зависит от порядка элементов
        (``06_AGGREGATOR_ADAPTERS.md`` §83).
        """
        exchanges = sorted(set(self._collect_exchanges(best_route)))
        protocol = "+".join(exchanges) if exchanges else "velora_aggregate"
        return (
            RouteStep(
                input_token=request.input_token.key,
                output_token=request.output_token.key,
                protocol=protocol,
            ),
        )

    def _collect_exchanges(self, node: Any) -> list[str]:
        """Рекурсивно собрать названия обменников."""
        if isinstance(node, dict):
            found: list[str] = []
            exchange = node.get("exchange")
            if exchange:
                found.append(str(exchange))
            for value in node.values():
                if isinstance(value, list | dict):
                    found.extend(self._collect_exchanges(value))
            return found
        if isinstance(node, list):
            collected: list[str] = []
            for item in node:
                collected.extend(self._collect_exchanges(item))
            return collected
        return []
