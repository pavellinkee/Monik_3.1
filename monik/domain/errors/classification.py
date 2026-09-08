"""Классификация ошибок для retry-политики.

Retry-оркестрация принадлежит Resource Manager (``38_INTERFACES.md`` §91):
подсистемы не создают собственные циклы повторов. Здесь определяется только
правило «можно ли повторять», которым Resource Manager пользуется.
"""

from __future__ import annotations

from monik.domain.enums.errors import ErrorCategory, Retryability
from monik.domain.errors.base import ErrorInfo

__all__ = ["RETRYABLE_CATEGORIES", "is_retryable"]

#: Категории, которые допускают повтор без изменения контекста запроса.
RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    {
        ErrorCategory.NETWORK,
        ErrorCategory.TIMEOUT,
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.PROVIDER,
        ErrorCategory.RESOURCE,
        ErrorCategory.DATABASE,
    }
)


def is_retryable(error: ErrorInfo, *, attempts_used: int, max_attempts: int) -> bool:
    """Можно ли повторить операцию после этой ошибки.

    Правила:

    * повтор невозможен, если исчерпан бюджет попыток
      (``CLAUDE.md`` §32: бесконечные повторы запрещены);
    * ``NON_RETRYABLE`` не повторяется никогда — в частности, data errors
      и ошибки аутентификации, для которых повтор не изменит результат;
    * ``CONDITIONAL`` повторяется только для категорий, где повтор
      осмыслен: временный сбой провайдера, rate limit, нехватка ресурса,
      блокировка БД.
    """
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    if attempts_used < 0:
        raise ValueError("attempts_used must not be negative")
    if attempts_used >= max_attempts:
        return False
    if error.retryability is Retryability.NON_RETRYABLE:
        return False
    if error.retryability is Retryability.RETRYABLE:
        return True
    return error.category in RETRYABLE_CATEGORIES
