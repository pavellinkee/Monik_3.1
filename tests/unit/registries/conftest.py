"""Конфигурация для тестов реестров."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from monik.config import Configuration, parse_configuration
from tests.unit.config.conftest import VALID_ENV, base_document


def registry_document() -> dict[str, Any]:
    """Конфигурация с несколькими токенами и рангами."""
    document = copy.deepcopy(base_document())
    document["tokens"].extend(
        [
            {
                "network_id": "polygon",
                "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                "symbol": "WETH",
                "decimals": 18,
                "rank": 3,
            },
            {
                "network_id": "polygon",
                "address": "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
                "symbol": "LINK",
                "decimals": 18,
                "rank": 4,
                "enabled": False,
            },
        ]
    )
    return document


@pytest.fixture
def configuration() -> Configuration:
    return parse_configuration(registry_document(), environ=dict(VALID_ENV)).config
