"""Opportunity Service — подтверждение, снимок и постановка доставки."""

from monik.services.opportunity.ports import (
    ConfirmationPublisher,
    MessageRenderer,
    NotificationLog,
    OpportunityStatusStore,
    PublishedNotification,
    SequenceSource,
)
from monik.services.opportunity.service import (
    ConfirmationOutcome,
    DeliveryOutcome,
    OpportunityService,
    delivery_status_for,
)
from monik.services.opportunity.snapshot import build_snapshot
from monik.services.opportunity.statistics import ConfirmationStatistics

__all__ = [
    "ConfirmationOutcome",
    "ConfirmationPublisher",
    "ConfirmationStatistics",
    "DeliveryOutcome",
    "MessageRenderer",
    "NotificationLog",
    "OpportunityService",
    "OpportunityStatusStore",
    "PublishedNotification",
    "SequenceSource",
    "build_snapshot",
    "delivery_status_for",
]
