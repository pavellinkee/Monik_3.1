"""Normalized application errors (``18_ERROR_HANDLING.md``, ``29_ERROR_HANDLING.md``).

Все подсистемы используют единую модель ошибки. Infrastructure переводит
исключения внешних библиотек в эти типы на своей границе, чтобы
provider-specific классы не распространялись в domain и application layer.
"""

from monik.domain.errors.application import (
    CalculationError,
    CancellationError,
    ConfigurationError,
    DomainValidationError,
    InternalError,
)
from monik.domain.errors.base import ErrorInfo, MonikError
from monik.domain.errors.classification import RETRYABLE_CATEGORIES, is_retryable
from monik.domain.errors.infrastructure import (
    AuthenticationError,
    DatabaseError,
    DataError,
    NetworkError,
    ProviderError,
    RateLimitError,
    ResourceError,
    TimeoutError,
    UnsupportedError,
)

__all__ = [
    "RETRYABLE_CATEGORIES",
    "AuthenticationError",
    "CalculationError",
    "CancellationError",
    "ConfigurationError",
    "DataError",
    "DatabaseError",
    "DomainValidationError",
    "ErrorInfo",
    "InternalError",
    "MonikError",
    "NetworkError",
    "ProviderError",
    "RateLimitError",
    "ResourceError",
    "TimeoutError",
    "UnsupportedError",
    "is_retryable",
]
