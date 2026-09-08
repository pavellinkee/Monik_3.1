"""Источники цены газа.

Решение D-4: ``GasPriceProvider`` — независимая абстракция. Конкретный
источник (RPC, внешний gas API, статическое значение для тестов)
подключается конфигурацией и заменяется без изменения бизнес-логики.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Protocol, runtime_checkable

from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import DataError
from monik.domain.models.gas import GasPrice
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.domain.value_objects.identifiers import RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.http import HttpClient, HttpRequest, classify_response
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = [
    "RPC_RESOURCE_OWNER",
    "GasPriceProvider",
    "RpcGasPriceProvider",
    "StaticGasPriceProvider",
]

#: Имя ресурса blockchain RPC в Resource Manager.
RPC_RESOURCE_OWNER = "rpc"


@runtime_checkable
class GasPriceProvider(Protocol):
    """Источник текущей цены газа сети."""

    async def gas_price(self, network_id: NetworkId) -> GasPrice | None:
        """Текущая цена газа или ``None``, если она недоступна.

        ``None`` означает «неизвестно» и **не** эквивалентно нулю
        (``09_PROFIT_CALCULATOR.md`` §16).
        """
        ...


class StaticGasPriceProvider:
    """Фиксированная цена газа.

    **Test implementation** (``CLAUDE.md`` §10, §46): применяется в тестах и
    как явно настроенный fallback, а не как источник production-данных.
    """

    def __init__(self, clock: Clock, *, prices: dict[str, int]) -> None:
        self._clock = clock
        self._prices = dict(prices)

    async def gas_price(self, network_id: NetworkId) -> GasPrice | None:
        """Настроенная цена сети."""
        wei = self._prices.get(str(network_id))
        if wei is None:
            return None
        return GasPrice(
            network_id=network_id,
            wei_per_gas=wei,
            source="static",
            observed_at=self._clock.now(),
        )


class RpcGasPriceProvider:
    """Цена газа из JSON-RPC узла сети.

    Поддерживает EIP-1559: при доступности ``baseFeePerGas`` итоговая цена
    складывается из base fee и priority fee. Внешний вызов выполняется через
    Resource Manager (``CLAUDE.md`` §14).
    """

    def __init__(
        self,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        rpc_urls: dict[str, str],
        freshness_seconds: int,
        priority_fee_wei: int = 30_000_000_000,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._http = http
        self._resources = resources
        self._clock = clock
        self._rpc_urls = dict(rpc_urls)
        self._freshness = timedelta(seconds=freshness_seconds)
        self._priority_fee_wei = priority_fee_wei
        self._timeout = timedelta(seconds=timeout_seconds)

    async def gas_price(self, network_id: NetworkId) -> GasPrice | None:
        """Запросить цену газа у RPC."""
        url = self._rpc_urls.get(str(network_id))
        if url is None:
            return None
        payload = await self._call(url, network_id, "eth_gasPrice")
        legacy = self._parse_quantity(payload, field="eth_gasPrice")
        if legacy is None:
            return None
        base_fee = await self._base_fee(url, network_id)
        now = self._clock.now()
        if base_fee is None:
            return GasPrice(
                network_id=network_id,
                wei_per_gas=legacy,
                source="rpc:eth_gasPrice",
                observed_at=now,
                expires_at=now + self._freshness,
            )
        return GasPrice(
            network_id=network_id,
            wei_per_gas=base_fee + self._priority_fee_wei,
            base_fee_wei=base_fee,
            priority_fee_wei=self._priority_fee_wei,
            source="rpc:eth_feeHistory",
            observed_at=now,
            expires_at=now + self._freshness,
        )

    async def _base_fee(self, url: str, network_id: NetworkId) -> int | None:
        """Base fee последнего блока, если сеть поддерживает EIP-1559."""
        payload = await self._call(url, network_id, "eth_feeHistory", ["0x1", "latest", []])
        if not isinstance(payload, dict):
            return None
        base_fees = payload.get("baseFeePerGas")
        if not isinstance(base_fees, list) or not base_fees:
            return None
        return self._parse_hex(str(base_fees[-1]), field="baseFeePerGas")

    async def _call(
        self,
        url: str,
        network_id: NetworkId,
        method: str,
        params: list[Any] | None = None,
    ) -> Any:
        """Выполнить JSON-RPC вызов через Resource Manager."""
        request_id = RequestId.generate()
        resource_request = ResourceRequest(
            request_id=request_id,
            key=ResourceKey(
                # RPC — самостоятельный внешний ресурс, а не агрегатор
                # (``01_PROJECT_REQUIREMENTS.md`` §34).
                provider_id=RPC_RESOURCE_OWNER,
                network_id=network_id,
                operation=CapabilityOperation.GAS_ESTIMATE,
            ),
            priority=RequestPriority.MAINTENANCE,
            timeout=self._timeout,
            created_at=self._clock.now(),
            sequence=0,
            deduplication_key=f"rpc:{network_id}:{method}",
        )

        async def call() -> Any:
            response = await self._http.send(
                HttpRequest(
                    method="POST",
                    url=url,
                    json_body={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": method,
                        "params": params or [],
                    },
                    request_id=request_id,
                    timeout_seconds=self._timeout.total_seconds(),
                )
            )
            classify_response(response, provider="rpc")
            body = response.json()
            if not isinstance(body, dict):
                raise DataError("rpc response is not a JSON object", code="rpc_response_malformed")
            return body.get("result")

        return await self._resources.execute(resource_request, call)

    def _parse_quantity(self, payload: Any, *, field: str) -> int | None:
        if payload is None:
            return None
        return self._parse_hex(str(payload), field=field)

    @staticmethod
    def _parse_hex(value: str, *, field: str) -> int:
        """Разобрать шестнадцатеричное значение JSON-RPC."""
        try:
            return int(value, 16)
        except ValueError as exc:
            raise DataError(
                f"rpc returned a malformed quantity in {field!r}",
                code="rpc_quantity_invalid",
            ) from exc
