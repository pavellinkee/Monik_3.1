"""Категории и severity нормализованных ошибок."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class ErrorCategory(DomainEnum):
    """Категория ошибки (``18_ERROR_HANDLING.md`` §3, ``CLAUDE.md`` §31).

    ``DATA`` выделен отдельно: некорректные данные провайдера никогда не должны
    превращаться в валидный quote (``CLAUDE.md`` §12).
    """

    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    DATA = "data"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PROVIDER = "provider"
    UNSUPPORTED = "unsupported"
    DATABASE = "database"
    RESOURCE = "resource"
    CALCULATION = "calculation"
    CANCELLATION = "cancellation"
    INTERNAL = "internal"


class ErrorSeverity(DomainEnum):
    """Severity ошибки (``18_ERROR_HANDLING.md`` §17-18)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Retryability(DomainEnum):
    """Классификация повторяемости (``18_ERROR_HANDLING.md`` §33-36).

    ``CONDITIONAL`` означает, что решение зависит от контекста
    (например, наличие ``Retry-After`` или оставшегося retry budget).
    """

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    CONDITIONAL = "conditional"
