"""Canonical domain models (``36_DATA_MODELS.md``).

Каждая сущность имеет ровно одно каноническое представление в домене.
Infrastructure-специфичные представления (ответы провайдеров, строки БД,
Telegram DTO) преобразуются в эти модели на соответствующей границе.

Наименование сущности Level 1 зафиксировано решением D-1
(``DEVELOPMENT_PLAN.md`` §9): результат Level 1 — :class:`Opportunity`,
а :class:`Candidate` — промежуточный результат до прохождения проверок.
"""

from monik.domain.models.base import DomainModel
from monik.domain.models.capability import Capability, CapabilityKey
from monik.domain.models.confirmation import AmountSnapshot, ConfirmationSnapshot
from monik.domain.models.conversion import ConversionRate
from monik.domain.models.fee import Fee, FeeKey, FeeSnapshot
from monik.domain.models.gas import Gas, GasPrice
from monik.domain.models.health import ApplicationHealth, ComponentHealth, ProviderHealth
from monik.domain.models.job import (
    AmountVerificationResult,
    ConfirmationResult,
    Level2Attempt,
    Level2Job,
)
from monik.domain.models.network import Network
from monik.domain.models.notification import (
    Notification,
    NotificationAttempt,
    NotificationDestination,
)
from monik.domain.models.opportunity import (
    Candidate,
    Opportunity,
    OpportunityAmount,
    RouteSnapshot,
)
from monik.domain.models.profit import (
    PROFIT_FORMULA_VERSION,
    CostBreakdown,
    ProfitCalculationInput,
    ProfitResult,
    ThresholdOutcome,
)
from monik.domain.models.provider import Provider
from monik.domain.models.quote import Quote
from monik.domain.models.resource import ResourceKey, ResourceRequest, ResourceResult
from monik.domain.models.route import Route, RouteStep
from monik.domain.models.scan import Scan, ScanScope, ScanStatistics
from monik.domain.models.scheduler import (
    SchedulerExecution,
    SchedulerTask,
    SchedulerTaskState,
)
from monik.domain.models.token import Token, TokenKey
from monik.domain.models.transitions import StateTransitionRecord

__all__ = [
    "AmountSnapshot",
    "SchedulerTaskState",
    "StateTransitionRecord",
    "ConfirmationSnapshot",
    "PROFIT_FORMULA_VERSION",
    "AmountVerificationResult",
    "ApplicationHealth",
    "Candidate",
    "Capability",
    "CapabilityKey",
    "ComponentHealth",
    "ConfirmationResult",
    "ConversionRate",
    "CostBreakdown",
    "DomainModel",
    "Fee",
    "FeeKey",
    "FeeSnapshot",
    "Gas",
    "GasPrice",
    "Level2Attempt",
    "Level2Job",
    "Network",
    "Notification",
    "NotificationAttempt",
    "NotificationDestination",
    "Opportunity",
    "OpportunityAmount",
    "ProfitCalculationInput",
    "ProfitResult",
    "Provider",
    "ProviderHealth",
    "Quote",
    "ResourceKey",
    "ResourceRequest",
    "ResourceResult",
    "Route",
    "RouteSnapshot",
    "RouteStep",
    "Scan",
    "ScanScope",
    "ScanStatistics",
    "SchedulerExecution",
    "SchedulerTask",
    "ThresholdOutcome",
    "Token",
    "TokenKey",
]
