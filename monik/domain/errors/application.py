"""Ошибки уровня приложения и домена."""

from __future__ import annotations

from monik.domain.enums.errors import ErrorCategory, ErrorSeverity, Retryability
from monik.domain.errors.base import MonikError

__all__ = [
    "CalculationError",
    "CancellationError",
    "ConfigurationError",
    "DomainValidationError",
    "InternalError",
]


class ConfigurationError(MonikError):
    """Некорректная или неполная конфигурация.

    Приложение не должно запускать критические подсистемы с невалидной
    конфигурацией и не должно молча подставлять безопасные на вид значения
    (``17_CONFIGURATION.md`` §10-11).
    """

    category = ErrorCategory.CONFIGURATION
    severity = ErrorSeverity.CRITICAL
    retryability = Retryability.NON_RETRYABLE
    default_code = "configuration_invalid"


class DomainValidationError(MonikError):
    """Нарушение инварианта доменной модели."""

    category = ErrorCategory.VALIDATION
    severity = ErrorSeverity.ERROR
    retryability = Retryability.NON_RETRYABLE
    default_code = "validation_failed"


class CalculationError(MonikError):
    """Ошибка финансового расчёта.

    Calculator обязан вернуть явную ошибку, а не произвольное число
    (``09_PROFIT_CALCULATOR.md`` §72-73).
    """

    category = ErrorCategory.CALCULATION
    severity = ErrorSeverity.ERROR
    retryability = Retryability.NON_RETRYABLE
    default_code = "calculation_failed"


class CancellationError(MonikError):
    """Операция отменена.

    Отмена не является сбоем: она не должна повышать счётчики ошибок и
    не запускает новую работу (``35_STATE_MACHINES.md`` §130).
    """

    category = ErrorCategory.CANCELLATION
    severity = ErrorSeverity.INFO
    retryability = Retryability.NON_RETRYABLE
    default_code = "cancelled"


class InternalError(MonikError):
    """Непредвиденная внутренняя ошибка."""

    category = ErrorCategory.INTERNAL
    severity = ErrorSeverity.CRITICAL
    retryability = Retryability.NON_RETRYABLE
    default_code = "internal_error"
