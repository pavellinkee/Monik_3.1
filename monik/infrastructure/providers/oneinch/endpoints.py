"""Endpoints и параметры API 1inch.

⚠️ **API contract NOT verified against live endpoint.**
Решение D-3 (``DEVELOPMENT_PLAN.md`` §9): в среде разработки обращение к
``api.1inch.dev`` заблокировано, а ключей нет. Контракт собран по
документированному описанию Classic Swap API и подлежит подтверждению
скриптом ``scripts/verify_provider_api.py`` в среде с доступом и ключом.

Все provider-specific детали собраны в этом модуле, поэтому корректировка
после live-проверки затрагивает один файл
(``06_AGGREGATOR_ADAPTERS.md`` §3, §87).
"""

from __future__ import annotations

from monik.domain.value_objects.identity import NetworkId

__all__ = [
    "API_VERSION",
    "DEFAULT_BASE_URL",
    "SUPPORTED_CHAIN_IDS",
    "chain_id_for",
    "liquidity_sources_path",
    "quote_path",
    "tokens_path",
]

#: Базовый URL Classic Swap API.
DEFAULT_BASE_URL = "https://api.1inch.dev"

#: Версия Swap API, используемая адаптером.
API_VERSION = "v6.1"

#: Сети, поддержка которых заявлена адаптером, и их chain id.
#: Приём chain id самим API не считается подтверждением поддержки
#: (``06_AGGREGATOR_ADAPTERS.md`` §15).
SUPPORTED_CHAIN_IDS: dict[str, int] = {
    "polygon": 137,
}


def chain_id_for(network_id: NetworkId) -> int | None:
    """Chain id сети или ``None``, если сеть не заявлена."""
    return SUPPORTED_CHAIN_IDS.get(str(network_id))


def quote_path(chain_id: int) -> str:
    """Путь получения котировки."""
    return f"/swap/{API_VERSION}/{chain_id}/quote"


def tokens_path(chain_id: int) -> str:
    """Путь получения списка поддерживаемых токенов."""
    return f"/swap/{API_VERSION}/{chain_id}/tokens"


def liquidity_sources_path(chain_id: int) -> str:
    """Путь получения списка источников ликвидности."""
    return f"/swap/{API_VERSION}/{chain_id}/liquidity-sources"
