"""Источники курса токена в базовой валюте расчёта.

Решение D-4: ``TokenPriceProvider`` — независимая абстракция. Бизнес-логика
не привязана к конкретному внешнему поставщику цен; источник подключается
конфигурацией и заменяется без изменения Profit Calculator.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Protocol, runtime_checkable

from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.operations import OperationType
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import DataError, MonikError
from monik.domain.models.conversion import ConversionRate
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.domain.models.token import Token
from monik.domain.value_objects.identifiers import RequestId
from monik.infrastructure.http import HttpClient, HttpRequest, classify_response
from monik.infrastructure.providers.contract import AggregatorAdapter, QuoteRequest
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger
from monik.services.resources import ResourceManager

__all__ = [
    "PRICE_RESOURCE_OWNER",
    "AggregatorQuotePriceProvider",
    "HttpPriceProvider",
    "StaticPriceProvider",
    "TokenPriceProvider",
]

_LOGGER = get_logger("services.prices")

#: Имя ресурса внешнего price API в Resource Manager.
PRICE_RESOURCE_OWNER = "prices"


@runtime_checkable
class TokenPriceProvider(Protocol):
    """Источник курса ``from_token -> to_token``."""

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Курс конверсии или ``None``, если он недоступен.

        ``None`` означает «неизвестно» и не подменяется выдуманным
        значением (``09_PROFIT_CALCULATOR.md`` §37).
        """
        ...


class StaticPriceProvider:
    """Фиксированные курсы.

    **Test implementation** (``CLAUDE.md`` §10, §46).
    """

    def __init__(
        self, clock: Clock, *, rates: dict[tuple[str, str], Decimal], ttl_seconds: int = 300
    ) -> None:
        self._clock = clock
        self._rates = dict(rates)
        self._ttl = timedelta(seconds=ttl_seconds)

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Настроенный курс пары."""
        value = self._rates.get((str(from_token.key), str(to_token.key)))
        if value is None:
            return None
        now = self._clock.now()
        return ConversionRate(
            from_token=from_token.key,
            to_token=to_token.key,
            rate=value,
            source="static",
            observed_at=now,
            expires_at=now + self._ttl,
        )


class AggregatorQuotePriceProvider:
    """Курс из котировки уже подключённого агрегатора.

    Не требует отдельного внешнего сервиса: цена native token в валюте
    расчёта берётся из executable quote, а не из абстрактной market price
    (``01_PROJECT_REQUIREMENTS.md`` §17).
    """

    def __init__(
        self,
        adapter: AggregatorAdapter,
        clock: Clock,
        *,
        probe_amount_raw: int,
        ttl_seconds: int = 300,
    ) -> None:
        if probe_amount_raw <= 0:
            raise ValueError("probe amount must be positive")
        self._adapter = adapter
        self._clock = clock
        self._probe_amount_raw = probe_amount_raw
        self._ttl = timedelta(seconds=ttl_seconds)

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Получить курс через котировку агрегатора."""
        request = QuoteRequest(
            network_id=from_token.network_id,
            operation=OperationType.SELL,
            input_token=from_token,
            output_token=to_token,
            input_amount=from_token.amount_from_base_units(self._probe_amount_raw),
            request_id=RequestId.generate(),
            priority=RequestPriority.MAINTENANCE,
        )
        try:
            quote = await self._adapter.get_quote(request)
        except MonikError as error:
            _LOGGER.info("price quote unavailable: %s", error.info.code)
            return None
        if quote.input_amount.as_decimal == 0 or quote.output_amount.is_zero():
            return None
        now = self._clock.now()
        return ConversionRate(
            from_token=from_token.key,
            to_token=to_token.key,
            rate=quote.output_amount.as_decimal / quote.input_amount.as_decimal,
            source=f"quote:{self._adapter.provider_id.value}",
            observed_at=now,
            expires_at=now + self._ttl,
        )


class HttpPriceProvider:
    """Курс из внешнего price API.

    Конкретный сервис задаётся конфигурацией (CoinGecko, DeFiLlama и др.):
    бизнес-логика от него не зависит. Запрос проходит через Resource Manager
    (``CLAUDE.md`` §14).
    """

    def __init__(
        self,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        endpoint: str,
        ttl_seconds: int = 300,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._http = http
        self._resources = resources
        self._clock = clock
        self._endpoint = endpoint.rstrip("/")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._timeout = timedelta(seconds=timeout_seconds)

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Запросить курс у внешнего сервиса."""
        request_id = RequestId.generate()
        resource_request = ResourceRequest(
            request_id=request_id,
            key=ResourceKey(
                provider_id=PRICE_RESOURCE_OWNER,
                network_id=from_token.network_id,
                operation=CapabilityOperation.TOKEN_METADATA,
            ),
            priority=RequestPriority.MAINTENANCE,
            timeout=self._timeout,
            created_at=self._clock.now(),
            sequence=0,
            deduplication_key=f"price:{from_token.key}:{to_token.key}",
        )

        async def call() -> Decimal | None:
            response = await self._http.send(
                HttpRequest(
                    method="GET",
                    url=self._endpoint,
                    params={
                        "network": str(from_token.network_id),
                        "from": str(from_token.address),
                        "to": str(to_token.address),
                    },
                    request_id=request_id,
                    timeout_seconds=self._timeout.total_seconds(),
                )
            )
            classify_response(response, provider=PRICE_RESOURCE_OWNER)
            body = response.json()
            if not isinstance(body, dict):
                raise DataError(
                    "price response is not a JSON object", code="price_response_malformed"
                )
            raw = body.get("rate")
            if raw is None:
                return None
            if isinstance(raw, float):
                raise DataError(
                    "price response returned a binary float rate",
                    code="price_value_invalid",
                )
            return Decimal(str(raw))

        try:
            value = await self._resources.execute(resource_request, call)
        except MonikError as error:
            _LOGGER.info("price api unavailable: %s", error.info.code)
            return None
        if value is None or value <= 0:
            return None
        now = self._clock.now()
        return ConversionRate(
            from_token=from_token.key,
            to_token=to_token.key,
            rate=value,
            source="http",
            observed_at=now,
            expires_at=now + self._ttl,
        )
