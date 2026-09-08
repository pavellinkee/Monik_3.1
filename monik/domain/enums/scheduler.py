"""Scheduler: режимы задач и политика пересечения запусков."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class TaskMode(DomainEnum):
    """Режим планирования задачи (``14_SCHEDULER.md`` §12-15, ``CLAUDE.md`` §22)."""

    STARTUP = "startup"
    INTERVAL = "interval"
    DAILY = "daily"
    MANUAL = "manual"


class OverlapPolicy(DomainEnum):
    """Поведение при наложении запусков (``14_SCHEDULER.md`` §27-31).

    Для Level 1 по умолчанию действует ``SKIP``
    (``02_LEVEL1_SCANNER.md`` §65).
    """

    SKIP = "skip"
    QUEUE = "queue"
    ALLOW_CONCURRENT = "allow_concurrent"
