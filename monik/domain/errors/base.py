"""Нормализованная модель ошибки и базовое исключение.

Infrastructure переводит исключения провайдеров, HTTP и БД в этот вид на
своей границе (``38_INTERFACES.md`` §82): наружу в domain и application
не должны выходить provider-specific классы исключений
(``38_INTERFACES.md`` §12).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import Field

from monik.domain.enums.errors import ErrorCategory, ErrorSeverity, Retryability
from monik.domain.models.base import DomainModel
from monik.domain.value_objects.identifiers import CorrelationId, RequestId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["ErrorInfo", "MonikError"]


class ErrorInfo(DomainModel):
    """Сериализуемое описание ошибки (``36_DATA_MODELS.md`` §64).

    Provider-specific диагностика хранится в необязательных полях и не
    является частью обязательного контракта (``36_DATA_MODELS.md`` §65).
    Секреты сюда не помещаются никогда.
    """

    code: str = Field(min_length=1, max_length=64)
    category: ErrorCategory
    severity: ErrorSeverity
    retryability: Retryability
    message: str = Field(min_length=1, max_length=512)
    subsystem: str | None = Field(default=None, max_length=64)
    operation: str | None = Field(default=None, max_length=64)
    occurred_at: UtcDatetime | None = None
    correlation_id: CorrelationId | None = None
    request_id: RequestId | None = None
    provider_code: str | None = Field(default=None, max_length=128)
    http_status: int | None = Field(default=None, ge=100, le=599)
    retry_after: timedelta | None = None

    @property
    def is_retryable(self) -> bool:
        """Можно ли повторить операцию.

        ``CONDITIONAL`` не считается безусловно повторяемым: решение
        принимает Resource Manager с учётом retry budget и ``Retry-After``
        (``18_ERROR_HANDLING.md`` §36-39).
        """
        return self.retryability is Retryability.RETRYABLE


class MonikError(Exception):
    """Базовое исключение Monik.

    Каждое исключение несёт нормализованное :class:`ErrorInfo`, поэтому
    ошибку можно залогировать, сохранить и передать между подсистемами
    без потери классификации.

    Подклассы задают ``category``, ``severity`` и ``retryability`` по
    умолчанию; конкретное место возникновения уточняет остальные поля.
    """

    category: ErrorCategory = ErrorCategory.INTERNAL
    severity: ErrorSeverity = ErrorSeverity.ERROR
    retryability: Retryability = Retryability.NON_RETRYABLE
    default_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        subsystem: str | None = None,
        operation: str | None = None,
        occurred_at: Any = None,
        correlation_id: CorrelationId | None = None,
        request_id: RequestId | None = None,
        provider_code: str | None = None,
        http_status: int | None = None,
        retry_after: timedelta | None = None,
        severity: ErrorSeverity | None = None,
        retryability: Retryability | None = None,
    ) -> None:
        super().__init__(message)
        self.info = ErrorInfo(
            code=code or self.default_code,
            category=self.category,
            severity=severity or self.severity,
            retryability=retryability or self.retryability,
            message=message[:512],
            subsystem=subsystem,
            operation=operation,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            request_id=request_id,
            provider_code=provider_code,
            http_status=http_status,
            retry_after=retry_after,
        )

    @property
    def code(self) -> str:
        """Машиночитаемый код ошибки."""
        return self.info.code

    @property
    def is_retryable(self) -> bool:
        """Является ли ошибка безусловно повторяемой."""
        return self.info.is_retryable

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.info.code!r}, message={self.info.message!r})"
