"""Ошибки внешних систем: сеть, провайдеры, база данных, ресурсы.

Ключевое различие (``06_AGGREGATOR_ADAPTERS.md`` §75-77): ``UNSUPPORTED``
означает отсутствие поддержки, а timeout, 429 и 5xx — временный сбой при
существующей поддержке. Смешивать их запрещено: временная ошибка не должна
превращать capability в ``UNSUPPORTED``.
"""

from __future__ import annotations

from monik.domain.enums.errors import ErrorCategory, ErrorSeverity, Retryability
from monik.domain.errors.base import MonikError

__all__ = [
    "AuthenticationError",
    "DataError",
    "DatabaseError",
    "NetworkError",
    "ProviderError",
    "RateLimitError",
    "ResourceError",
    "TimeoutError",
    "UnsupportedError",
]


class NetworkError(MonikError):
    """Транспортная ошибка при обращении к внешней системе."""

    category = ErrorCategory.NETWORK
    severity = ErrorSeverity.WARNING
    retryability = Retryability.RETRYABLE
    default_code = "network_error"


class TimeoutError(MonikError):  # noqa: A001 - доменное имя важнее совпадения с builtin
    """Истёк таймаут операции.

    Таймаут не означает отсутствие поддержки операции
    (``06_AGGREGATOR_ADAPTERS.md`` §77) и не является признаком убыточности
    (``11_LEVEL_2_SCANNER.md`` §53).
    """

    category = ErrorCategory.TIMEOUT
    severity = ErrorSeverity.WARNING
    retryability = Retryability.RETRYABLE
    default_code = "timeout"


class RateLimitError(MonikError):
    """Превышен лимит запросов.

    Обрабатывается Resource Manager с учётом ``Retry-After``
    (``CLAUDE.md`` §32). Не является ``UNSUPPORTED`` и не означает
    убыточность (``11_LEVEL_2_SCANNER.md`` §55).
    """

    category = ErrorCategory.RATE_LIMIT
    severity = ErrorSeverity.WARNING
    retryability = Retryability.CONDITIONAL
    default_code = "rate_limited"


class AuthenticationError(MonikError):
    """Ошибка аутентификации у внешнего провайдера.

    Повторять бессмысленно до исправления конфигурации
    (``05_RESOURCE_MANAGER.md`` §28). Сообщение не должно содержать
    сам ключ или заголовок авторизации.
    """

    category = ErrorCategory.AUTHENTICATION
    severity = ErrorSeverity.CRITICAL
    retryability = Retryability.NON_RETRYABLE
    default_code = "authentication_failed"


class ProviderError(MonikError):
    """Ошибка, о которой сообщил сам провайдер."""

    category = ErrorCategory.PROVIDER
    severity = ErrorSeverity.WARNING
    retryability = Retryability.CONDITIONAL
    default_code = "provider_error"


class DataError(MonikError):
    """Некорректные или неполные данные во внешнем ответе.

    Data error никогда не превращается в валидный quote
    (``CLAUDE.md`` §12, ``06_AGGREGATOR_ADAPTERS.md`` §10): повтор
    такого запроса не исправит содержимое ответа.
    """

    category = ErrorCategory.DATA
    severity = ErrorSeverity.ERROR
    retryability = Retryability.NON_RETRYABLE
    default_code = "invalid_provider_data"


class UnsupportedError(MonikError):
    """Операция, сеть или токен действительно не поддерживаются.

    Отличается от временного сбоя (``06_AGGREGATOR_ADAPTERS.md`` §75).
    """

    category = ErrorCategory.UNSUPPORTED
    severity = ErrorSeverity.INFO
    retryability = Retryability.NON_RETRYABLE
    default_code = "unsupported"


class DatabaseError(MonikError):
    """Ошибка работы с persistent storage.

    Критический сбой persistence переводит систему в SAFE_STOP
    (``CLAUDE.md`` §34), поэтому severity по умолчанию — критическая.
    """

    category = ErrorCategory.DATABASE
    severity = ErrorSeverity.CRITICAL
    retryability = Retryability.CONDITIONAL
    default_code = "database_error"


class ResourceError(MonikError):
    """Запрос отклонён Resource Manager.

    Например: переполнена очередь, открыт circuit breaker, исчерпан
    retry budget (``12_RESOURCE_MANAGER.md`` §42-43).
    """

    category = ErrorCategory.RESOURCE
    severity = ErrorSeverity.WARNING
    retryability = Retryability.CONDITIONAL
    default_code = "resource_unavailable"
