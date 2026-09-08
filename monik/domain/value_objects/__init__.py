"""Domain value objects с точной числовой и строковой семантикой.

Здесь находятся типы, из которых собираются canonical models: идентичность
сети и токена, идентификаторы сущностей, точные числовые типы, timezone-aware
временные метки и детерминированные отпечатки.
"""

from monik.domain.value_objects.amounts import MAX_TOKEN_DECIMALS, Percentage, TokenAmount
from monik.domain.value_objects.fingerprints import (
    Fingerprint,
    NotificationFingerprint,
    OpportunityFingerprint,
    RouteFingerprint,
    compute_fingerprint,
)
from monik.domain.value_objects.identifiers import (
    CorrelationId,
    KId,
    OpportunityId,
    RequestId,
    ScanId,
    VId,
)
from monik.domain.value_objects.identity import NetworkId, TokenAddress, TokenSymbol
from monik.domain.value_objects.numeric import (
    BaseUnits,
    FloatNotAllowedError,
    NonNegativeDecimal,
    PositiveDecimal,
    SignedDecimal,
    to_decimal,
)
from monik.domain.value_objects.strings import ValidatedStr
from monik.domain.value_objects.timestamps import UtcDatetime, ensure_utc

__all__ = [
    "MAX_TOKEN_DECIMALS",
    "BaseUnits",
    "CorrelationId",
    "Fingerprint",
    "FloatNotAllowedError",
    "KId",
    "NetworkId",
    "NonNegativeDecimal",
    "NotificationFingerprint",
    "OpportunityFingerprint",
    "OpportunityId",
    "Percentage",
    "PositiveDecimal",
    "RequestId",
    "RouteFingerprint",
    "ScanId",
    "SignedDecimal",
    "TokenAddress",
    "TokenAmount",
    "TokenSymbol",
    "UtcDatetime",
    "VId",
    "ValidatedStr",
    "compute_fingerprint",
    "ensure_utc",
    "to_decimal",
]
