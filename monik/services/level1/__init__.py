"""Level 1 Scanner — поиск потенциальных возможностей на свежих котировках.

Level 1 находит кандидата и фиксирует маршрут; Level 2 подтверждает именно
этот маршрут (``10_LEVEL_1_SCANNER.md`` §95).
"""

from monik.services.level1.cycle import TokenCycle
from monik.services.level1.dedup import DeduplicationGuard
from monik.services.level1.filters import CombinationFilter, capability_operation
from monik.services.level1.grouping import CandidateGroup, group_candidates
from monik.services.level1.handoff import OpportunityHandoff
from monik.services.level1.ports import (
    FeeSource,
    GasSource,
    IdSequenceSource,
    Level2Dispatcher,
    OpportunityStore,
    RateSource,
    ScanStore,
)
from monik.services.level1.preliminary import PreliminaryEvaluator
from monik.services.level1.quotes import QuoteAttempt, QuoteCollector, QuoteStatistics
from monik.services.level1.ranking import rank_groups
from monik.services.level1.results import ScanResult
from monik.services.level1.scanner import Level1Scanner
from monik.services.level1.scope import ScopeBuilder
from monik.services.level1.validation import quote_rejection_reason

__all__ = [
    "CandidateGroup",
    "CombinationFilter",
    "DeduplicationGuard",
    "FeeSource",
    "GasSource",
    "IdSequenceSource",
    "Level1Scanner",
    "Level2Dispatcher",
    "OpportunityHandoff",
    "OpportunityStore",
    "PreliminaryEvaluator",
    "QuoteAttempt",
    "QuoteCollector",
    "QuoteStatistics",
    "RateSource",
    "ScanResult",
    "ScanStore",
    "ScopeBuilder",
    "TokenCycle",
    "capability_operation",
    "group_candidates",
    "quote_rejection_reason",
    "rank_groups",
]
