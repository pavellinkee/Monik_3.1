"""Нормализация ответов провайдеров в доменные модели.

Adapter обязан преобразовать provider-specific ответ в единый формат
(``06_AGGREGATOR_ADAPTERS.md`` §8) и проверить его целостность до создания
котировки (``06_AGGREGATOR_ADAPTERS.md`` §34-37): несоответствие токена,
сети или суммы делает ответ невалидным, а не «почти правильным».

Нормализация детерминирована и не зависит от порядка полей в JSON
(``06_AGGREGATOR_ADAPTERS.md`` §83).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from monik.domain.enums.operations import RoutingMode
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import DataError
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route, RouteStep
from monik.domain.models.token import Token, TokenKey
from monik.domain.value_objects.amounts import Percentage, TokenAmount
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.providers.contract import QuoteRequest

__all__ = [
    "build_quote",
    "build_single_step_route",
    "parse_base_units",
    "parse_optional_decimal",
    "require_field",
]


def require_field(payload: dict[str, Any], name: str, *, provider: ProviderId) -> Any:
    """Прочитать обязательное поле ответа.

    Отсутствие критических данных — ошибка данных
    (``06_AGGREGATOR_ADAPTERS.md`` §34).
    """
    if name not in payload or payload[name] is None:
        raise DataError(
            f"{provider.value} response is missing required field {name!r}",
            code="provider_field_missing",
            provider_code=provider.value,
        )
    return payload[name]


def parse_base_units(value: Any, *, provider: ProviderId, field: str) -> int:
    """Разобрать raw blockchain amount.

    Значение принимается только как целое или строка целого: ``float``
    потерял бы точность (``09_PROFIT_CALCULATOR.md`` §4).
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise DataError(
            f"{provider.value} returned a non-integer amount in {field!r}",
            code="provider_amount_invalid",
            provider_code=provider.value,
        )
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text.lstrip("-").isdigit():
            raise DataError(
                f"{provider.value} returned a malformed amount in {field!r}",
                code="provider_amount_invalid",
                provider_code=provider.value,
            )
        parsed = int(text)
    else:
        raise DataError(
            f"{provider.value} returned an unsupported amount type in {field!r}",
            code="provider_amount_invalid",
            provider_code=provider.value,
        )
    if parsed < 0:
        raise DataError(
            f"{provider.value} returned a negative amount in {field!r}",
            code="provider_amount_invalid",
            provider_code=provider.value,
        )
    return parsed


def parse_optional_decimal(value: Any, *, provider: ProviderId, field: str) -> Decimal | None:
    """Разобрать необязательное точное значение.

    Отсутствие значения возвращается как ``None`` и **не** превращается
    в ноль (``CLAUDE.md`` §12).
    """
    if value is None:
        return None
    if isinstance(value, float):
        raise DataError(
            f"{provider.value} returned a binary float in {field!r}",
            code="provider_value_invalid",
            provider_code=provider.value,
        )
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DataError(
            f"{provider.value} returned a malformed decimal in {field!r}",
            code="provider_value_invalid",
            provider_code=provider.value,
        ) from exc


def build_single_step_route(
    *,
    provider_id: ProviderId,
    request: QuoteRequest,
    routing_mode: RoutingMode,
    protocol: str,
    pool_address: str | None = None,
    provider_parameters: tuple[tuple[str, str], ...] = (),
) -> Route:
    """Построить простой одношаговый маршрут.

    Используется, когда API не раскрывает промежуточные пулы. Фиктивные
    шаги при этом не выдумываются (``06_AGGREGATOR_ADAPTERS.md`` §39).
    """
    return Route(
        provider_id=provider_id,
        network_id=request.network_id,
        operation=request.operation,
        routing_mode=routing_mode,
        input_token=request.input_token.key,
        output_token=request.output_token.key,
        steps=(
            RouteStep(
                input_token=request.input_token.key,
                output_token=request.output_token.key,
                protocol=protocol,
                pool_address=pool_address,
            ),
        ),
        provider_parameters=provider_parameters,
    )


def build_quote(
    *,
    provider_id: ProviderId,
    request: QuoteRequest,
    output_raw: int,
    route: Route,
    created_at: UtcDatetime,
    expires_at: UtcDatetime | None = None,
    estimated_gas_units: int | None = None,
    price_impact: Decimal | None = None,
    slippage_bps: int | None = None,
    provider_metadata: tuple[tuple[str, str], ...] = (),
    output_includes_fees: bool | None = None,
) -> Quote:
    """Собрать нормализованную котировку с проверкой целостности.

    Проверяются соответствие сети, токенов и суммы
    (``06_AGGREGATOR_ADAPTERS.md`` §35-37). Нулевой output допускается на
    уровне модели, но валидной прибыльной возможностью не является
    (``02_LEVEL1_SCANNER.md`` §25) — решение принимает Scanner.
    """
    _validate_route(provider_id=provider_id, request=request, route=route)
    try:
        return Quote(
            provider_id=provider_id,
            network_id=request.network_id,
            operation=request.operation,
            input_token=request.input_token.key,
            output_token=request.output_token.key,
            input_amount=request.input_amount,
            output_amount=TokenAmount(raw=output_raw, decimals=request.output_token.decimals),
            route=route,
            created_at=created_at,
            request_id=RequestId(str(request.request_id)),
            expires_at=expires_at,
            estimated_gas_units=estimated_gas_units,
            price_impact=Percentage(value=price_impact) if price_impact is not None else None,
            slippage_bps=slippage_bps,
            provider_metadata=provider_metadata,
            raw_output_amount_includes_fees=output_includes_fees,
        )
    except ValueError as exc:
        raise DataError(
            f"{provider_id.value} response could not be normalized: {exc}",
            code="provider_response_inconsistent",
            provider_code=provider_id.value,
        ) from exc


def _validate_route(*, provider_id: ProviderId, request: QuoteRequest, route: Route) -> None:
    """Убедиться, что маршрут описывает запрошенную операцию."""
    if route.provider_id is not provider_id:
        raise DataError(
            f"{provider_id.value} returned a route of another provider",
            code="provider_route_mismatch",
            provider_code=provider_id.value,
        )
    if route.network_id != request.network_id:
        raise DataError(
            f"{provider_id.value} returned a route for another network",
            code="provider_network_mismatch",
            provider_code=provider_id.value,
        )
    if route.operation is not request.operation:
        raise DataError(
            f"{provider_id.value} returned a route for another operation",
            code="provider_operation_mismatch",
            provider_code=provider_id.value,
        )
    _validate_token(provider_id, route.input_token, request.input_token, "input")
    _validate_token(provider_id, route.output_token, request.output_token, "output")


def _validate_token(provider_id: ProviderId, actual: TokenKey, expected: Token, label: str) -> None:
    if actual != expected.key:
        raise DataError(
            f"{provider_id.value} returned a different {label} token than requested",
            code="provider_token_mismatch",
            provider_code=provider_id.value,
        )
