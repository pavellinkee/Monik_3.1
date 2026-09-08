"""Общие данные для тестов конфигурации."""

from __future__ import annotations

import copy
from typing import Any

import pytest

USDT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
AAVE_ADDRESS = "0xD6DF932A45C0f255f85145f286eA0b292B21C90B"
WMATIC_ADDRESS = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"

VALID_ENV: dict[str, str] = {
    "MONIK_ONEINCH_API_KEY": "oneinch-example-key-value",
    "MONIK_ZEROX_API_KEY": "zerox-example-key-value",
}


def base_document() -> dict[str, Any]:
    """Минимальная валидная конфигурация."""
    return {
        "application": {"environment": "development", "timezone": "Europe/Lisbon"},
        "networks": [
            {
                "network_id": "polygon",
                "name": "Polygon",
                "chain_id": 137,
                "native_token_symbol": "POL",
                "wrapped_native_address": WMATIC_ADDRESS,
                "enabled": True,
            }
        ],
        "providers": [
            {
                "provider_id": "oneinch",
                "enabled": True,
                "api_key": {"env": "MONIK_ONEINCH_API_KEY"},
                "supported_networks": ["polygon"],
            },
            {
                "provider_id": "zero_x",
                "enabled": True,
                "api_key": {"env": "MONIK_ZEROX_API_KEY"},
                "supported_networks": ["polygon"],
            },
        ],
        "tokens": [
            {
                "network_id": "polygon",
                "address": USDT_ADDRESS,
                "symbol": "USDT",
                "decimals": 6,
                "rank": 1,
            },
            {
                "network_id": "polygon",
                "address": AAVE_ADDRESS,
                "symbol": "AAVE",
                "decimals": 18,
                "rank": 2,
            },
        ],
        "scanner": {
            "base_network": "polygon",
            "base_token_address": USDT_ADDRESS,
            "amounts": ["100", "500"],
        },
    }


@pytest.fixture
def document() -> dict[str, Any]:
    """Изолированная копия базового документа."""
    return copy.deepcopy(base_document())


@pytest.fixture
def env() -> dict[str, str]:
    """Изолированная копия валидного окружения."""
    return dict(VALID_ENV)
