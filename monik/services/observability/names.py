"""Имена метрик Monik.

Централизованный список удерживает набор метрик стабильным и
предсказуемым (``28_OBSERVABILITY.md`` §29-40): подсистемы не изобретают
собственных имён.
"""

from __future__ import annotations

__all__ = [
    "DB_OPERATION_SECONDS",
    "LEVEL1_OPPORTUNITIES",
    "LEVEL1_QUOTE_FAILURES",
    "LEVEL1_QUOTE_REQUESTS",
    "LEVEL1_SCANS",
    "LEVEL1_SCAN_SECONDS",
    "LEVEL2_AMOUNTS",
    "LEVEL2_JOBS",
    "LEVEL2_SECONDS",
    "NOTIFICATIONS",
    "PROVIDER_LATENCY_SECONDS",
    "QUEUE_DEPTH",
    "SCHEDULER_EXECUTIONS",
    "SCHEDULER_SECONDS",
]

#: Циклы Level 1 по итоговому статусу (``28`` §30).
LEVEL1_SCANS = "level1_scans"

#: Длительность цикла Level 1.
LEVEL1_SCAN_SECONDS = "level1_scan"

#: Запросы котировок Level 1 по провайдеру и операции.
LEVEL1_QUOTE_REQUESTS = "level1_quote_requests"

#: Неуспешные запросы котировок Level 1.
LEVEL1_QUOTE_FAILURES = "level1_quote_failures"

#: Созданные возможности (``28`` §30).
LEVEL1_OPPORTUNITIES = "level1_opportunities"

#: Проверки Level 2 по итоговому статусу (``28`` §31).
LEVEL2_JOBS = "level2_jobs"

#: Результаты проверки отдельных сумм.
LEVEL2_AMOUNTS = "level2_amounts"

#: Длительность подтверждения Level 2.
LEVEL2_SECONDS = "level2_confirmation"

#: Уведомления по исходу доставки (``28`` §37).
NOTIFICATIONS = "notifications"

#: Запуски задач планировщика по статусу (``28`` §39).
SCHEDULER_EXECUTIONS = "scheduler_executions"

#: Длительность задачи планировщика.
SCHEDULER_SECONDS = "scheduler_task"

#: Задержка провайдера (``28`` §35).
PROVIDER_LATENCY_SECONDS = "provider_latency"

#: Глубина очереди (``28`` §29).
QUEUE_DEPTH = "queue_depth"

#: Длительность операций базы данных (``28`` §38).
DB_OPERATION_SECONDS = "db_operation"
