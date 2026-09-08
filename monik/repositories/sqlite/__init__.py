"""SQLite implementations. Единственное место с SQL.

Проверяется architecture-тестом: raw SQL и драйвер SQLite не используются
за пределами этого пакета и ``monik.infrastructure.db``.
"""

from monik.repositories.sqlite.capabilities import SqliteCapabilityRepository
from monik.repositories.sqlite.confirmations import (
    PublishedNotification,
    SqliteConfirmationRepository,
)
from monik.repositories.sqlite.fees import SqliteFeeRepository, SqliteGasRepository
from monik.repositories.sqlite.jobs import SqliteJobRepository
from monik.repositories.sqlite.metadata import SqliteMetadataRepository
from monik.repositories.sqlite.notifications import SqliteNotificationRepository
from monik.repositories.sqlite.opportunities import SqliteOpportunityRepository
from monik.repositories.sqlite.scans import SqliteScanRepository
from monik.repositories.sqlite.scheduler import (
    SchedulerTaskState,
    SqliteSchedulerRepository,
)
from monik.repositories.sqlite.sequences import (
    JOB_SEQUENCE,
    NOTIFICATION_SEQUENCE,
    OPPORTUNITY_SEQUENCE,
    SqliteIdSequenceRepository,
)
from monik.repositories.sqlite.state_transitions import (
    SqliteStateTransitionRepository,
    StateTransitionRecord,
)

__all__ = [
    "JOB_SEQUENCE",
    "NOTIFICATION_SEQUENCE",
    "OPPORTUNITY_SEQUENCE",
    "PublishedNotification",
    "SchedulerTaskState",
    "SqliteCapabilityRepository",
    "SqliteConfirmationRepository",
    "SqliteFeeRepository",
    "SqliteGasRepository",
    "SqliteIdSequenceRepository",
    "SqliteJobRepository",
    "SqliteMetadataRepository",
    "SqliteNotificationRepository",
    "SqliteOpportunityRepository",
    "SqliteScanRepository",
    "SqliteSchedulerRepository",
    "SqliteStateTransitionRepository",
    "StateTransitionRecord",
]
