"""Endpoints и параметры Uniswap Trading API.

Контракт соответствует актуальному Trading API v1
(``POST https://trade-api.gateway.uniswap.org/v1/quote``):

* обязательные поля запроса — ``type``, ``amount``, ``tokenInChainId``,
  ``tokenOutChainId``, ``tokenIn``, ``tokenOut``, ``swapper``;
* ровно один механизм проскальзывания — ``slippageTolerance`` **или**
  ``autoSlippage``; запрос без обоих API отклоняет;
* ``routingPreference`` принимает ``BEST_PRICE`` или ``FASTEST``.
  Значения ``CLASSIC``/``UNISWAPX`` относятся к прежнему
  unified-routing-api и в запросе больше не используются.

Значение ``routing`` из **ответа** — отдельная величина: оно описывает,
какой механизм фактически выбрал API, и сохраняется как часть identity
маршрута. Classic и UniswapX нельзя молча объединять в один тип маршрута
(``06_AGGREGATOR_ADAPTERS.md`` §26-27).
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.operations import RoutingMode
from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "API_KEY_HEADER",
    "AUTO_SLIPPAGE_DEFAULT",
    "DEFAULT_BASE_URL",
    "DEFAULT_ROUTING_PREFERENCE",
    "HEALTH_PROBES",
    "POLYGON_ROUTING_MODES",
    "QUOTE_PATH",
    "ROUTING_MODES",
    "ROUTING_PREFERENCES",
    "SUPPORTED_CHAIN_IDS",
    "HealthProbe",
    "chain_id_for",
    "routing_mode_for",
]

#: Базовый URL Trading API.
DEFAULT_BASE_URL = "https://trade-api.gateway.uniswap.org"

#: Заголовок с ключом доступа.
API_KEY_HEADER = "x-api-key"

#: Путь получения котировки. Запрос выполняется методом POST.
QUOTE_PATH = "/v1/quote"

#: Сети, поддержка которых заявлена адаптером.
SUPPORTED_CHAIN_IDS: dict[str, int] = {
    "polygon": 137,
}

#: Соответствие значений ``routing`` из ответа нормализованным режимам.
#: Отсутствующий в этом списке режим не подменяется другим: неизвестное
#: значение делает ответ непригодным (``06_AGGREGATOR_ADAPTERS.md`` §26).
ROUTING_MODES: dict[str, RoutingMode] = {
    "CLASSIC": RoutingMode.CLASSIC,
    "DUTCH_LIMIT": RoutingMode.UNISWAPX_DUTCH_V2,
    "DUTCH_V2": RoutingMode.UNISWAPX_DUTCH_V2,
    "DUTCH_V3": RoutingMode.UNISWAPX_DUTCH_V3,
    "PRIORITY": RoutingMode.UNISWAPX_PRIORITY,
}

#: Режимы маршрутизации, доступные на Polygon.
#:
#: UniswapX на Polygon не развёрнут: Dutch V2 работает на Mainnet, Arbitrum
#: и Base, Dutch V3 — только на Arbitrum. Заявлять их поддержку означало бы
#: объявить возможность, которой нет (``06_AGGREGATOR_ADAPTERS.md`` §15).
POLYGON_ROUTING_MODES: frozenset[RoutingMode] = frozenset({RoutingMode.CLASSIC})

#: Допустимые значения ``routingPreference`` в запросе.
ROUTING_PREFERENCES: frozenset[str] = frozenset({"BEST_PRICE", "FASTEST"})

#: Значение по умолчанию: лучший курс, а не самый быстрый маршрут.
DEFAULT_ROUTING_PREFERENCE = "BEST_PRICE"

#: Значение ``autoSlippage``, при котором проскальзывание выбирает API.
AUTO_SLIPPAGE_DEFAULT = "DEFAULT"


@dataclass(frozen=True, slots=True)
class HealthProbe:
    """Параметры минимального запроса проверки доступности API.

    Health check обязан отправлять **валидный** запрос котировки: иначе
    единственным ответом API будет постоянная ошибка 400, а провайдер
    навсегда останется в состоянии DEGRADED. Свопы, подписи и изменение
    состояния не выполняются (``01_PROJECT_REQUIREMENTS.md`` §55).
    """

    chain_id: int
    token_in: str
    token_out: str
    amount: str


#: Проверочные пары по сетям. Адреса — канонические контракты Polygon:
#: USDT ``0xc2132D05...`` и native USDC ``0x3c499c54...``. Это публичные
#: константы сети, а не секреты и не выдуманные значения.
HEALTH_PROBES: dict[str, HealthProbe] = {
    "polygon": HealthProbe(
        chain_id=137,
        token_in="0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        token_out="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        # 1 USDT (6 знаков): минимальная сумма, для которой маршрут
        # заведомо существует.
        amount="1000000",
    ),
}


def chain_id_for(network_id: NetworkId) -> int | None:
    """Chain id сети или ``None``, если сеть не заявлена."""
    return SUPPORTED_CHAIN_IDS.get(str(network_id))


def routing_mode_for(routing: str) -> RoutingMode | None:
    """Нормализованный режим маршрутизации ответа или ``None``.

    Разбирается ответ, а не запрос: адаптер фиксирует, какой механизм
    выбрал API, и не подменяет неизвестное значение известным.
    """
    return ROUTING_MODES.get(routing.strip().upper())
