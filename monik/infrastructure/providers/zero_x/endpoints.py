"""Endpoints и параметры Swap API 0x.

⚠️ **API contract NOT verified against live endpoint** (решение D-3):
``api.0x.org`` в среде разработки недоступен, ключей нет. Контракт собран по
документированному описанию Swap API v2 (allowance-holder) и подлежит
подтверждению скриптом ``scripts/verify_provider_api.py``.
"""

from __future__ import annotations

from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "API_VERSION",
    "API_KEY_HEADER",
    "API_VERSION_HEADER",
    "DEFAULT_BASE_URL",
    "PRICE_PATH",
    "SOURCES_PATH",
    "SUPPORTED_CHAIN_IDS",
    "chain_id_for",
]

#: Базовый URL Swap API.
DEFAULT_BASE_URL = "https://api.0x.org"

#: Версия Swap API.
API_VERSION = "v2"

#: Заголовок, в котором передаётся версия API.
API_VERSION_HEADER = "0x-version"

#: Заголовок с ключом доступа.
API_KEY_HEADER = "0x-api-key"

#: Индикативная цена: не создаёт ордер и не требует taker.
#: Monik не выполняет свопы (``01_PROJECT_REQUIREMENTS.md`` §55), поэтому
#: используется именно этот endpoint, а не ``/quote``.
PRICE_PATH = "/swap/allowance-holder/price"

#: Список источников ликвидности сети.
SOURCES_PATH = "/sources"

#: Сети, поддержка которых заявлена адаптером.
SUPPORTED_CHAIN_IDS: dict[str, int] = {
    "polygon": 137,
}


def chain_id_for(network_id: NetworkId) -> int | None:
    """Chain id сети или ``None``, если сеть не заявлена."""
    return SUPPORTED_CHAIN_IDS.get(str(network_id))
