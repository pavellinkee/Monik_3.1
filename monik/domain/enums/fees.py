"""Категории, статусы и признак включённости комиссий."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class FeeType(DomainEnum):
    """Категория стоимости (``36_DATA_MODELS.md`` §25, ``07_FEE_SYSTEM.md`` §4).

    ``REBATE`` хранится отдельным компонентом и не смешивается с обычной fee
    (``09_PROFIT_CALCULATOR.md`` §15).
    """

    AGGREGATOR = "aggregator"
    PROTOCOL = "protocol"
    INTEGRATOR = "integrator"
    NETWORK = "network"
    SERVICE = "service"
    REBATE = "rebate"
    OTHER = "other"


class FeeStatus(DomainEnum):
    """Достоверность значения комиссии (``13_FEE_SYSTEM.md`` §7-11).

    ``UNKNOWN`` никогда не эквивалентен нулю (``CLAUDE.md`` §23,
    ``07_FEE_SYSTEM.md`` §15). ``KNOWN`` с нулевой суммой означает
    подтверждённое отсутствие комиссии, что не то же самое, что ``UNKNOWN``.
    """

    KNOWN = "known"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    EXPIRED = "expired"
    ERROR = "error"


class CostInclusion(DomainEnum):
    """Учтён ли cost уже в output amount quote (``09_PROFIT_CALCULATOR.md`` §45-46).

    Нужен для защиты от двойного учёта. ``UNKNOWN`` не позволяет считать
    расчёт полным.
    """

    INCLUDED_IN_QUOTE = "included_in_quote"
    NOT_INCLUDED = "not_included"
    UNKNOWN = "unknown"
