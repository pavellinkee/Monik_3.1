"""Capability Registry: операции и их состояния."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class CapabilityOperation(DomainEnum):
    """Проверяемая возможность provider/network/token комбинации.

    Набор соответствует ``08_CAPABILITY_REGISTRY.md`` §21 и
    ``20_CAPABILITY_REGISTRY.md`` §56-59.
    """

    QUOTE_BUY = "quote_buy"
    QUOTE_SELL = "quote_sell"
    FIXED_ROUTE = "fixed_route"
    FEE_DISCOVERY = "fee_discovery"
    TOKEN_METADATA = "token_metadata"
    GAS_ESTIMATE = "gas_estimate"


class CapabilityStatus(DomainEnum):
    """Состояние capability.

    ``UNKNOWN`` никогда не эквивалентен ``SUPPORTED``
    (``36_DATA_MODELS.md`` §61, ``08_CAPABILITY_REGISTRY.md`` §10).
    ``STALE`` означает истёкшую свежесть, а не отсутствие поддержки.
    Временная недоступность (``UNAVAILABLE``/``DEGRADED``) не превращается
    в ``UNSUPPORTED`` (``06_AGGREGATOR_ADAPTERS.md`` §77).
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    CHECKING = "checking"
    FAILED = "failed"
