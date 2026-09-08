"""Adapter Uniswap Trading API.

Запрос строится по актуальному контракту ``POST /v1/quote`` (см.
:mod:`monik.infrastructure.providers.uniswap.endpoints`): обязательный
``swapper``, ровно один механизм проскальзывания и ``routingPreference``
из набора ``BEST_PRICE``/``FASTEST``.

Ключевая особенность разбора ответа: Uniswap различает Classic и семейство
UniswapX. Эти режимы **не объединяются** — routing mode является частью
identity маршрута (``06_AGGREGATOR_ADAPTERS.md`` §26-27), поэтому маршрут,
полученный в другом режиме, не считается тем же самым маршрутом.

Monik остаётся потребителем котировок: адаптер не подписывает транзакции,
не выполняет свопы и не хранит приватных ключей
(``01_PROJECT_REQUIREMENTS.md`` §55). ``swapper`` — публичный адрес,
задаваемый конфигурацией, а не секрет.
"""

from __future__ import annotations

import json
from decimal import Decimal
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
from monik.domain.errors import (
    ConfigurationError,
    DataError,
    MonikError,
    UnsupportedError,
)
from monik.domain.models.fee import Fee
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route, RouteStep
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.http import HttpClient, HttpResponse
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

__all__ = [
    "OPTION_AUTO_SLIPPAGE",
    "OPTION_ROUTING_PREFERENCE",
    "OPTION_SLIPPAGE_TOLERANCE_PERCENT",
    "OPTION_SWAPPER",
    "UniswapAdapter",
]

_PROVIDER = ProviderId.UNISWAP

#: Trading API позволяет задать предпочтение маршрутизации, но не принимает
#: конкретный маршрут как входной параметр, поэтому воспроизведение
#: проверяется сравнением отпечатков (``06_AGGREGATOR_ADAPTERS.md`` §51).
_SUPPORTS_FIXED_ROUTE = False

#: Публичный адрес, от имени которого API строит котировку. Обязательное
#: поле запроса; подпись и приватный ключ не требуются и не используются.
OPTION_SWAPPER = "swapper"

#: ``BEST_PRICE`` или ``FASTEST``.
OPTION_ROUTING_PREFERENCE = "routing_preference"

#: Постоянный допуск проскальзывания в процентах, если Monik не передал
#: собственное значение в ``QuoteRequest``.
OPTION_SLIPPAGE_TOLERANCE_PERCENT = "slippage_tolerance_percent"

#: ``true`` — доверить выбор проскальзывания API (``autoSlippage``).
OPTION_AUTO_SLIPPAGE = "auto_slippage"

#: Поля тела ошибки, которые Trading API использует для диагностики.
_ERROR_FIELDS = ("errorCode", "detail", "message", "error")

#: Ограничение длины диагностики: в сообщение об ошибке не должно попадать
#: произвольно большое тело ответа.
_ERROR_DETAIL_LIMIT = 300


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
            # Адаптер заявлен только для Polygon, где UniswapX не развёрнут:
            # объявлять Dutch/Priority означало бы заявить возможность,
            # которой нет (``06_AGGREGATOR_ADAPTERS.md`` §15).
            routing_modes=endpoints.POLYGON_ROUTING_MODES,
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
        """Проверить доступность API минимальным **валидным** запросом.

        Отправляется полноценная котировка на небольшую сумму: неполный
        запрос API отвергает с 400, и провайдер выглядел бы недоступным
        всегда. Своп не выполняется, транзакция не подписывается
        (``01_PROJECT_REQUIREMENTS.md`` §55).
        """
        name, probe = next(iter(endpoints.HEALTH_PROBES.items()))
        try:
            swapper = self._swapper()
        except ConfigurationError as error:
            # Отсутствующая настройка — не сетевой сбой, но и работать
            # адаптер не может: сообщаем причину, а не ложную готовность.
            return AdapterHealth(
                provider_id=_PROVIDER,
                state=AdapterState.DEGRADED,
                detail=error.info.code,
            )
        body: dict[str, Any] = {
            "type": "EXACT_INPUT",
            "amount": probe.amount,
            "tokenInChainId": probe.chain_id,
            "tokenOutChainId": probe.chain_id,
            "tokenIn": probe.token_in,
            "tokenOut": probe.token_out,
            "swapper": swapper,
            "routingPreference": self._routing_preference(),
        }
        body.update(self._slippage_fields(None))
        try:
            await self.request_json(
                path=endpoints.QUOTE_PATH,
                network_id=NetworkId(name),
                operation=CapabilityOperation.QUOTE_BUY,
                request_id=RequestId.generate(),
                method="POST",
                json_body=body,
                deduplication_key=f"uniswap:health:{probe.chain_id}",
            )
        except MonikError as error:
            return AdapterHealth(
                provider_id=_PROVIDER,
                state=AdapterState.DEGRADED,
                detail=error.info.code,
            )
        return AdapterHealth(provider_id=_PROVIDER, state=AdapterState.READY)

    def error_detail(self, response: HttpResponse) -> str | None:
        """Диагностика отклонённого запроса Trading API.

        Без неё ошибка 400 сообщает только код статуса, и причина отказа
        (неизвестный токен, отсутствующий маршрут, некорректный параметр)
        теряется. В сообщение попадают только документированные поля
        ошибки, обрезанные по длине и пропущенные через редакцию секретов:
        сырое тело ответа и заголовки не раскрываются
        (``22_SECURITY.md``).
        """
        try:
            body = json.loads(response.text)
        except (ValueError, TypeError):
            return None
        if not isinstance(body, dict):
            return None
        parts = [
            f"{field}={body[field]}"
            for field in _ERROR_FIELDS
            if isinstance(body.get(field), str | int)
        ]
        if not parts:
            return None
        return self.redact_provider_text(" ".join(parts))[:_ERROR_DETAIL_LIMIT]

    # --- построение запроса ----------------------------------------------

    def _quote_body(self, request: QuoteRequest, chain_id: int) -> dict[str, Any]:
        """Тело POST-запроса котировки.

        Все обязательные поля контракта присутствуют всегда, включая
        ``swapper`` и ровно один механизм проскальзывания.
        """
        body: dict[str, Any] = {
            "type": "EXACT_INPUT",
            "amount": str(request.input_amount.raw),
            "tokenInChainId": chain_id,
            "tokenOutChainId": chain_id,
            "tokenIn": str(request.input_token.address),
            "tokenOut": str(request.output_token.address),
            "swapper": self._swapper(),
            "routingPreference": self._routing_preference(),
        }
        body.update(self._slippage_fields(request.slippage_bps))
        return body

    def _swapper(self) -> str:
        """Публичный адрес из конфигурации провайдера.

        Адрес не выдумывается и не подставляется по умолчанию: котировка,
        построенная для произвольного адреса, не является достоверной
        (``CLAUDE.md`` §12).
        """
        swapper = self._config.option(OPTION_SWAPPER)
        if swapper is None:
            raise ConfigurationError(
                "uniswap adapter requires the public 'swapper' provider option",
                code="provider_swapper_not_configured",
                provider_code=_PROVIDER.value,
            )
        return swapper

    def _routing_preference(self) -> str:
        """Значение ``routingPreference`` запроса.

        Это API-specific предпочтение, а не внутреннее состояние Monik:
        режим маршрутизации найденного маршрута определяется **ответом**
        и хранится отдельно.
        """
        configured = self._config.option(OPTION_ROUTING_PREFERENCE)
        if configured is None:
            return endpoints.DEFAULT_ROUTING_PREFERENCE
        preference = configured.upper()
        if preference not in endpoints.ROUTING_PREFERENCES:
            raise ConfigurationError(
                f"unsupported uniswap routingPreference: {configured!r}",
                code="provider_routing_preference_invalid",
                provider_code=_PROVIDER.value,
            )
        return preference

    def _slippage_fields(self, slippage_bps: int | None) -> dict[str, Any]:
        """Ровно один механизм проскальзывания.

        API требует либо ``slippageTolerance``, либо ``autoSlippage``:
        запрос без обоих отклоняется, а с обоими — тем более. Проценты
        считаются точной арифметикой (``CLAUDE.md`` §11); во внешний JSON
        значение уходит одной сериализацией на границе.
        """
        percent = self._slippage_percent(slippage_bps)
        if percent is None:
            return {"autoSlippage": endpoints.AUTO_SLIPPAGE_DEFAULT}
        return {"slippageTolerance": float(percent)}

    def _slippage_percent(self, slippage_bps: int | None) -> Decimal | None:
        """Допуск проскальзывания в процентах либо ``None``.

        ``None`` означает «решает API»: собственную формулу адаптер не
        придумывает.
        """
        if slippage_bps is not None:
            return Decimal(slippage_bps) / Decimal(100)
        if _is_true(self._config.option(OPTION_AUTO_SLIPPAGE)):
            return None
        configured = self._config.option(OPTION_SLIPPAGE_TOLERANCE_PERCENT)
        if configured is None:
            return None
        try:
            return Decimal(configured)
        except ArithmeticError as error:
            raise ConfigurationError(
                f"invalid uniswap slippage_tolerance_percent: {configured!r}",
                code="provider_slippage_option_invalid",
                provider_code=_PROVIDER.value,
            ) from error

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
            provider_metadata=self._metadata(payload, routing_mode),
            output_includes_fees=True,
        )

    @staticmethod
    def _metadata(
        payload: dict[str, Any], routing_mode: RoutingMode
    ) -> tuple[tuple[str, str], ...]:
        """Сопровождающие данные ответа.

        ``requestId`` возвращается Trading API и нужен для диагностики
        обращений в поддержку; отсутствующее значение не подменяется.
        """
        metadata: list[tuple[str, str]] = [("routing", routing_mode.value)]
        request_id = payload.get("requestId")
        if isinstance(request_id, str) and request_id:
            metadata.append(("provider_request_id", request_id))
        return tuple(metadata)

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
        """Извлечь итоговую сумму из ``quote.output.amount``.

        Прежнего поля ``quote.quote`` в актуальном контракте нет: разбирать
        его означало бы принять ответ другого API за валидный
        (``CLAUDE.md`` §12).
        """
        output = require_field(quote_body, "output", provider=_PROVIDER)
        if not isinstance(output, dict):
            raise DataError(
                "uniswap quote output is not a JSON object",
                code="provider_response_malformed",
                provider_code=_PROVIDER.value,
            )
        return parse_base_units(
            require_field(output, "amount", provider=_PROVIDER),
            provider=_PROVIDER,
            field="output.amount",
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


def _is_true(value: str | None) -> bool:
    """Разбор булева provider-параметра конфигурации."""
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}
