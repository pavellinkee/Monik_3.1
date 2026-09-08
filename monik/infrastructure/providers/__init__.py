"""Aggregator adapters. Provider-specific код только здесь.

Каждый агрегатор изолирован собственным модулем
(``06_AGGREGATOR_ADAPTERS.md`` §3): изменение API одного провайдера не
затрагивает Level 1, Level 2, Scheduler, Resource Manager, Calculator и
Telegram.
"""

from monik.infrastructure.providers.contract import (
    AdapterCapabilities,
    AdapterHealth,
    AggregatorAdapter,
    QuoteRequest,
    RouteValidation,
)
from monik.infrastructure.providers.fake import FakeAdapter
from monik.infrastructure.providers.normalization import (
    build_quote,
    build_single_step_route,
    parse_base_units,
    parse_optional_decimal,
    require_field,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterHealth",
    "AggregatorAdapter",
    "FakeAdapter",
    "QuoteRequest",
    "RouteValidation",
    "build_quote",
    "build_single_step_route",
    "parse_base_units",
    "parse_optional_decimal",
    "require_field",
]
