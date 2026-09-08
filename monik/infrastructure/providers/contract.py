"""Общий контракт Aggregator Adapter.

Core работает с единым интерфейсом и не знает endpoints, формат JSON,
особенности аутентификации и правила комиссий конкретного провайдера
(``06_AGGREGATOR_ADAPTERS.md`` §2). Эти детали находятся только внутри
соответствующего адаптера.

Adapter не принимает бизнес-решений (``06_AGGREGATOR_ADAPTERS.md`` §84):
он не создаёт Opportunity, не применяет threshold, не подтверждает Level 2
и не отправляет уведомления.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol, runtime_checkable

from monik.domain.enums.health import AdapterState
from monik.domain.enums.operations import (
    OperationType,
    RouteValidationOutcome,
    RoutingMode,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.models.fee import Fee
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route
from monik.domain.models.token import Token
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.fingerprints import RouteFingerprint
from monik.domain.value_objects.identifiers import CorrelationId, RequestId
from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "AdapterCapabilities",
    "AdapterHealth",
    "AggregatorAdapter",
    "QuoteRequest",
    "RouteValidation",
]


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    """Нормализованный запрос котировки.

    Core передаёт доменные объекты, а не raw HTTP-параметры
    (``06_AGGREGATOR_ADAPTERS.md`` §5).

    ``fixed_route`` заполняется Level 2: адаптер обязан воспроизвести именно
    этот маршрут либо сообщить, что не может
    (``11_LEVEL_2_SCANNER.md`` §6).
    """

    network_id: NetworkId
    operation: OperationType
    input_token: Token
    output_token: Token
    input_amount: TokenAmount
    request_id: RequestId
    routing_mode: RoutingMode | None = None
    fixed_route: Route | None = None
    slippage_bps: int | None = None
    correlation_id: CorrelationId | None = None
    # Приоритет передаётся Resource Manager: Level 2 обслуживается раньше
    # Level 1 (``CLAUDE.md`` §15).
    priority: RequestPriority = RequestPriority.LEVEL1_BUY
    timeout: timedelta | None = None

    def __post_init__(self) -> None:
        if self.input_token.network_id != self.network_id:
            raise ValueError("quote request input token belongs to another network")
        if self.output_token.network_id != self.network_id:
            raise ValueError("quote request output token belongs to another network")
        if self.input_token.key == self.output_token.key:
            raise ValueError("quote request input and output tokens must differ")
        if self.input_amount.raw <= 0:
            raise ValueError("quote request amount must be positive")
        if self.input_amount.decimals != self.input_token.decimals:
            raise ValueError("quote request amount decimals do not match the input token")


@dataclass(frozen=True, slots=True)
class RouteValidation:
    """Результат проверки зафиксированного маршрута.

    ``MISMATCH`` и ``UNSUPPORTED`` различаются намеренно: невозможность
    воспроизвести маршрут не означает, что маршрут стал невыгодным
    (``11_LEVEL_2_SCANNER.md`` §51).
    """

    outcome: RouteValidationOutcome
    quote: Quote | None = None
    observed_fingerprint: RouteFingerprint | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is RouteValidationOutcome.REPRODUCED and self.quote is None:
            raise ValueError("reproduced route validation must carry the fresh quote")

    @property
    def is_reproduced(self) -> bool:
        """Удалось ли воспроизвести исходный маршрут."""
        return self.outcome is RouteValidationOutcome.REPRODUCED


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Что адаптер умеет по данным официального API.

    Поддержка сети не предполагается только потому, что API принимает
    идентификатор сети (``06_AGGREGATOR_ADAPTERS.md`` §15).
    """

    provider_id: ProviderId
    supported_networks: frozenset[NetworkId]
    routing_modes: frozenset[RoutingMode]
    supports_buy: bool = True
    supports_sell: bool = True
    supports_fixed_route: bool = False
    supports_fee_discovery: bool = False
    supports_gas_estimate: bool = False

    def supports_network(self, network_id: NetworkId) -> bool:
        """Поддерживается ли сеть."""
        return network_id in self.supported_networks

    def supports_operation(self, operation: OperationType) -> bool:
        """Поддерживается ли направление обмена."""
        return self.supports_buy if operation is OperationType.BUY else self.supports_sell


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    """Состояние адаптера.

    Health не равен capability (``06_AGGREGATOR_ADAPTERS.md`` §21):
    недоступность API не означает отсутствие поддержки операции.
    """

    provider_id: ProviderId
    state: AdapterState
    detail: str | None = None
    checked_operations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_usable(self) -> bool:
        """Можно ли отправлять запросы через адаптер."""
        return self.state in {AdapterState.READY, AdapterState.DEGRADED}


@runtime_checkable
class AggregatorAdapter(Protocol):
    """Единый интерфейс всех агрегаторов (``06_AGGREGATOR_ADAPTERS.md`` §4).

    Реализация обязана выполнять внешние запросы только через Resource
    Manager (``06_AGGREGATOR_ADAPTERS.md`` §31) и не создавать собственных
    циклов повторов (``06_AGGREGATOR_ADAPTERS.md`` §13).
    """

    @property
    def provider_id(self) -> ProviderId:
        """Идентификатор провайдера."""
        ...

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Статически известные возможности адаптера."""
        ...

    async def get_quote(self, request: QuoteRequest) -> Quote:
        """Получить свежую котировку.

        Возвращает нормализованный :class:`Quote`. Некорректный или неполный
        ответ приводит к ошибке данных, а не к «почти валидной» котировке
        (``06_AGGREGATOR_ADAPTERS.md`` §10).
        """
        ...

    async def validate_fixed_route(self, request: QuoteRequest) -> RouteValidation:
        """Проверить, воспроизводится ли зафиксированный маршрут."""
        ...

    async def discover_capabilities(self) -> AdapterCapabilities:
        """Уточнить возможности через API.

        Выполняется при старте и по расписанию, а не перед каждым scan
        (``06_AGGREGATOR_ADAPTERS.md`` §20).
        """
        ...

    async def discover_fees(self, network_id: NetworkId) -> tuple[Fee, ...]:
        """Получить raw информацию о комиссиях.

        Неизвестная комиссия возвращается со статусом ``UNKNOWN``, а не
        нулём (``06_AGGREGATOR_ADAPTERS.md`` §40).
        """
        ...

    async def health_check(self) -> AdapterHealth:
        """Проверить доступность API."""
        ...

    async def aclose(self) -> None:
        """Освободить ресурсы адаптера."""
        ...
