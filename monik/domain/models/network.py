"""Модель blockchain network."""

from __future__ import annotations

from pydantic import Field

from monik.domain.models.base import DomainModel
from monik.domain.value_objects.identity import NetworkId, TokenAddress, TokenSymbol

__all__ = ["Network"]


class Network(DomainModel):
    """Поддерживаемая сеть (``36_DATA_MODELS.md`` §7).

    Сеть не должна быть зашита в scanner logic — она приходит из
    configuration/capability layer (``01_PROJECT_REQUIREMENTS.md`` §6).
    """

    network_id: NetworkId
    name: str = Field(min_length=1, max_length=64)
    chain_id: int = Field(gt=0)
    native_token_symbol: TokenSymbol
    native_token_decimals: int = Field(ge=0, le=36)
    # Обёрнутый native token обязателен: он нужен для конвертации стоимости
    # gas в валюту расчёта, а native asset нельзя идентифицировать по символу
    # (36_DATA_MODELS.md §11).
    wrapped_native_address: TokenAddress
    enabled: bool = True
