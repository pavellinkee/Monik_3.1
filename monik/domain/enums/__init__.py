"""Stable domain enums, используемые в persistent state.

Значения enum'ов являются частью контракта БД и API: изменение значения
требует migration (``36_DATA_MODELS.md`` §76-78).
"""

from monik.domain.enums.base import DomainEnum
from monik.domain.enums.calculation import CalculationStatus, ThresholdMetric
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.errors import ErrorCategory, ErrorSeverity, Retryability
from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.health import (
    AdapterState,
    ApplicationHealthStatus,
    ProviderHealthStatus,
    SupervisorState,
)
from monik.domain.enums.lifecycle import (
    AmountConfirmationStatus,
    AmountVerificationStatus,
    JobStatus,
    NotificationStatus,
    OpportunityStatus,
    ScanStatus,
    TaskExecutionStatus,
)
from monik.domain.enums.notifications import (
    DeliveryErrorKind,
    DestinationKind,
    NotificationMode,
)
from monik.domain.enums.operations import (
    OperationType,
    RouteValidationOutcome,
    RoutingMode,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.quotes import QuoteStatus
from monik.domain.enums.resources import (
    CircuitState,
    RequestPriority,
    ResourceResultStatus,
    ResourceState,
)
from monik.domain.enums.scheduler import OverlapPolicy, TaskMode

__all__ = [
    "AdapterState",
    "AmountConfirmationStatus",
    "AmountVerificationStatus",
    "ApplicationHealthStatus",
    "CalculationStatus",
    "CapabilityOperation",
    "CapabilityStatus",
    "CircuitState",
    "CostInclusion",
    "DeliveryErrorKind",
    "DestinationKind",
    "DomainEnum",
    "ErrorCategory",
    "ErrorSeverity",
    "FeeStatus",
    "FeeType",
    "JobStatus",
    "NotificationMode",
    "NotificationStatus",
    "OperationType",
    "OpportunityStatus",
    "OverlapPolicy",
    "ProviderHealthStatus",
    "ProviderId",
    "SupervisorState",
    "QuoteStatus",
    "RequestPriority",
    "ResourceResultStatus",
    "ResourceState",
    "Retryability",
    "RouteValidationOutcome",
    "RoutingMode",
    "ScanStatus",
    "TaskExecutionStatus",
    "TaskMode",
    "ThresholdMetric",
]
