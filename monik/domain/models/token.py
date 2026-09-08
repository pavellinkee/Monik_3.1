"""Модель токена и его идентичность."""

from __future__ import annotations

from typing import Self

from pydantic import Field

from monik.domain.models.base import DomainModel
from monik.domain.value_objects.amounts import MAX_TOKEN_DECIMALS, TokenAmount
from monik.domain.value_objects.identity import NetworkId, TokenAddress, TokenSymbol

__all__ = ["Token", "TokenKey"]


class TokenKey(DomainModel):
    """Canonical identity токена: ``network_id + normalized_address``.

    Symbol идентификатором не является (``36_DATA_MODELS.md`` §10).
    """

    network_id: NetworkId
    address: TokenAddress

    def __str__(self) -> str:
        return f"{self.network_id}:{self.address}"


class Token(DomainModel):
    """Токен в конкретной сети (``36_DATA_MODELS.md`` §9).

    ``decimals`` хранится явно и никогда не выводится из символа
    (``01_PROJECT_REQUIREMENTS.md`` §10).
    """

    network_id: NetworkId
    address: TokenAddress
    symbol: TokenSymbol
    decimals: int = Field(ge=0, le=MAX_TOKEN_DECIMALS)
    enabled: bool = True

    @property
    def key(self) -> TokenKey:
        """Canonical identity токена."""
        return TokenKey(network_id=self.network_id, address=self.address)

    def amount_from_base_units(self, raw: int) -> TokenAmount:
        """Построить количество из raw blockchain amount."""
        return TokenAmount(raw=raw, decimals=self.decimals)

    def amount_from_decimal(self, value: str | int) -> TokenAmount:
        """Построить количество из человекочитаемого значения."""
        return TokenAmount.from_decimal(value, self.decimals)

    def same_as(self, other: Self) -> bool:
        """Совпадают ли токены по canonical identity."""
        return self.key == other.key
