"""Конфигурация token universe."""

from __future__ import annotations

from pydantic import Field

from monik.config.base import ConfigSection
from monik.domain.value_objects.identity import NetworkId, TokenAddress, TokenSymbol

__all__ = ["TokenConfig"]


class TokenConfig(ConfigSection):
    """Описание одного токена.

    Authoritative metadata живёт в Token Registry, но разрешённый набор
    задаётся конфигурацией (``17_CONFIGURATION.md`` §28-29).
    ``decimals`` указывается явно и не выводится из символа
    (``01_PROJECT_REQUIREMENTS.md`` §10).
    """

    network_id: NetworkId
    address: TokenAddress
    symbol: TokenSymbol
    decimals: int = Field(ge=0, le=36)
    enabled: bool = True
    rank: int | None = Field(default=None, ge=1)
