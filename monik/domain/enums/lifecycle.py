"""Статусы жизненного цикла ключевых сущностей Monik.

Разрешённые переходы определены в ``35_STATE_MACHINES.md`` и реализуются
отдельными state machine модулями; здесь фиксируется только набор состояний.
"""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class OpportunityStatus(DomainEnum):
    """Единый lifecycle Opportunity — сущности, создаваемой Level 1.

    Решение D-1 (``DEVELOPMENT_PLAN.md`` §9): ``Opportunity`` — официальное имя
    результата Level 1. Набор объединяет verification-статусы
    (``11_LEVEL_2_SCANNER.md`` §47) и notification-статусы
    (``35_STATE_MACHINES.md`` §59, ``30_DATABASE_SCHEMA.md`` §27).

    ``UNPROFITABLE`` и ``ROUTE_UNAVAILABLE`` намеренно различаются:
    невозможность воспроизвести маршрут не означает убыточность
    (``11_LEVEL_2_SCANNER.md`` §51).
    """

    CREATED = "created"
    VERIFYING = "verifying"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNPROFITABLE = "unprofitable"
    ROUTE_UNAVAILABLE = "route_unavailable"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOTIFIED = "notified"
    NOTIFIED_PARTIAL = "notified_partial"
    NOTIFIED_FAILED = "notified_failed"


class JobStatus(DomainEnum):
    """Состояния Level 2 Job (``35_STATE_MACHINES.md`` §8).

    ``RUNNING`` после аварийного рестарта не является доказательством успеха
    (``35_STATE_MACHINES.md`` §135) и обрабатывается recovery-политикой.
    """

    QUEUED = "queued"
    RUNNING = "running"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AmountVerificationStatus(DomainEnum):
    """Результат проверки Level 2 для одной конкретной суммы.

    Соответствует ``11_LEVEL_2_SCANNER.md`` §48.
    """

    VERIFIED_PROFITABLE = "verified_profitable"
    VERIFIED_UNPROFITABLE = "verified_unprofitable"
    UNKNOWN = "unknown"
    FAILED = "failed"
    EXPIRED = "expired"
    ROUTE_UNAVAILABLE = "route_unavailable"


class AmountConfirmationStatus(DomainEnum):
    """Confirmation-статус суммы в терминах ``CLAUDE.md`` §26.

    ``PARTIAL`` нельзя автоматически считать ``CONFIRMED``.
    Используется в confirmation rate (``CLAUDE.md`` §27), где ``PARTIAL``
    исключается из расчёта.
    """

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    PARTIAL = "partial"


class NotificationStatus(DomainEnum):
    """Состояния доставки одного logical notification (``35_STATE_MACHINES.md`` §68)."""

    QUEUED = "queued"
    SENDING = "sending"
    RETRY_WAIT = "retry_wait"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanStatus(DomainEnum):
    """Статус одного цикла Level 1 (``10_LEVEL_1_SCANNER.md`` §45).

    ``PARTIAL`` не считается полностью успешным scan'ом
    (``02_LEVEL1_SCANNER.md`` §54).
    """

    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskExecutionStatus(DomainEnum):
    """Статус одного запуска scheduled task (``35_STATE_MACHINES.md`` §82)."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
