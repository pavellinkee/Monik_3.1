"""Endpoints и параметры Uniswap Trading API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3):
``api.uniswap.org`` и ``api-docs.uniswap.org`` в среде разработки
недоступны. Контракт собран по документированному описанию Trading API
и подлежит подтверждению скриптом ``scripts/verify_provider_api.py``.

Routing modes сохраняются раздельно: Classic и UniswapX нельзя молча
объединять в один тип маршрута (``06_AGGREGATOR_ADAPTERS.md`` §26-27).
"""

from __future__ import annotations

from monik.domain.enums.operations import RoutingMode
from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "API_KEY_HEADER",
    "DEFAULT_BASE_URL",
    "QUOTE_PATH",
    "ROUTING_MODES",
    "SUPPORTED_CHAIN_IDS",
    "chain_id_for",
    "routing_mode_for",
    "routing_preference_for",
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

#: Значение ``routingPreference`` запроса для каждого нормализованного режима.
_ROUTING_PREFERENCES: dict[RoutingMode, str] = {
    RoutingMode.CLASSIC: "CLASSIC",
    RoutingMode.UNISWAPX_DUTCH_V2: "UNISWAPX",
    RoutingMode.UNISWAPX_DUTCH_V3: "UNISWAPX",
    RoutingMode.UNISWAPX_PRIORITY: "UNISWAPX",
}


def chain_id_for(network_id: NetworkId) -> int | None:
    """Chain id сети или ``None``, если сеть не заявлена."""
    return SUPPORTED_CHAIN_IDS.get(str(network_id))


def routing_mode_for(routing: str) -> RoutingMode | None:
    """Нормализованный режим маршрутизации или ``None``, если он неизвестен."""
    return ROUTING_MODES.get(routing.strip().upper())


def routing_preference_for(mode: RoutingMode | None) -> str:
    """Значение ``routingPreference`` для запроса.

    Без явного требования используется ``CLASSIC``: выбирать UniswapX
    самостоятельно адаптер не должен.
    """
    if mode is None:
        return "CLASSIC"
    return _ROUTING_PREFERENCES.get(mode, "CLASSIC")
