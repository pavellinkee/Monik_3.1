"""Notification System — доставка подтверждённых возможностей.

Подсистема не содержит бизнес-логики сканера и ничего не пересчитывает
(``15_NOTIFICATION_SYSTEM.md`` §5, §14).
"""

from monik.services.notifications.dispatcher import (
    DeliveryReport,
    NotificationDispatcher,
    details_callback_data,
)
from monik.services.notifications.formatter import DETAILS_BUTTON_LABEL, MessageFormatter
from monik.services.notifications.policy import SendDecision, mode_decision
from monik.services.notifications.ports import (
    DeliveryReceipt,
    NotificationStore,
    NotificationTransport,
    OutgoingMessage,
)

__all__ = [
    "DETAILS_BUTTON_LABEL",
    "DeliveryReceipt",
    "DeliveryReport",
    "MessageFormatter",
    "NotificationDispatcher",
    "NotificationStore",
    "NotificationTransport",
    "OutgoingMessage",
    "SendDecision",
    "details_callback_data",
    "mode_decision",
]
