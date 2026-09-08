"""Идентичность сети и токена.

Canonical token identity — ``network_id + normalized_address``
(``36_DATA_MODELS.md`` §10). Symbol идентификатором не является:
одинаковый символ может относиться к разным токенам в разных сетях
(``01_PROJECT_REQUIREMENTS.md`` §9).
"""

from __future__ import annotations

import re

from monik.domain.value_objects.strings import ValidatedStr

__all__ = ["NetworkId", "TokenAddress", "TokenSymbol"]

_NETWORK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")


class NetworkId(ValidatedStr):
    """Стабильный идентификатор сети, например ``polygon``.

    Display name идентификатором быть не может (``36_DATA_MODELS.md`` §8).
    """

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _NETWORK_ID_RE.fullmatch(normalized):
            raise ValueError(
                f"invalid network id: {value!r}; expected lowercase slug like 'polygon'"
            )
        return normalized


class TokenAddress(ValidatedStr):
    """Адрес токена в конкретной сети, нормализованный к нижнему регистру.

    Нормализация обязательна (``08_CAPABILITY_REGISTRY.md`` §30): один и тот же
    адрес в разном регистре должен давать одну и ту же identity.
    """

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EVM_ADDRESS_RE.fullmatch(normalized):
            raise ValueError(f"invalid EVM token address: {value!r}; expected 0x + 40 hex chars")
        return normalized


class TokenSymbol(ValidatedStr):
    """Отображаемый символ токена.

    Используется только для представления и диагностики; идентичностью
    токена не является.
    """

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not _SYMBOL_RE.fullmatch(normalized):
            raise ValueError(f"invalid token symbol: {value!r}")
        return normalized.upper()
