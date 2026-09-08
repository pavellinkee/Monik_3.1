"""Endpoints и параметры Velora (ранее ParaSwap) Market API.

⚠️ **API contract NOT verified against live endpoint** (решение D-3).
В среде разработки ``api.paraswap.io`` и ``developers.velora.xyz``
недоступны. Контракт собран по документированному описанию Market API
и подлежит подтверждению скриптом ``scripts/verify_provider_api.py``.

Решение D-5: ``provider_id`` — ``velora``; Velora является ребрендингом
ParaSwap, поэтому базовый URL остаётся ``api.paraswap.io`` до его
официальной смены. Значение переопределяется конфигурацией без изменения
кода.
"""

from __future__ import annotations

from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "API_VERSION",
    "DEFAULT_BASE_URL",
    "PRICES_PATH",
    "SUPPORTED_NETWORK_IDS",
    "TOKENS_PATH",
    "network_id_for",
    "tokens_path",
]

#: Базовый URL Market API.
DEFAULT_BASE_URL = "https://api.paraswap.io"

#: Версия Market API.
API_VERSION = "6.2"

#: Путь получения котировки.
PRICES_PATH = "/prices"

#: Путь получения списка токенов сети.
TOKENS_PATH = "/tokens"

#: Сети, поддержка которых заявлена адаптером, и их сетевые идентификаторы.
SUPPORTED_NETWORK_IDS: dict[str, int] = {
    "polygon": 137,
}


def network_id_for(network_id: NetworkId) -> int | None:
    """Сетевой идентификатор Velora или ``None``, если сеть не заявлена."""
    return SUPPORTED_NETWORK_IDS.get(str(network_id))


def tokens_path(network: int) -> str:
    """Путь списка токенов конкретной сети."""
    return f"{TOKENS_PATH}/{network}"
