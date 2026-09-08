"""Сквозной контекст корреляции.

Критические операции должны позволять связать записи логов одного workflow:
scan, opportunity, Level 2 job, запрос (``28_OBSERVABILITY.md``,
``CLAUDE.md`` §48). Контекст хранится в ``contextvars``, поэтому корректно
работает при конкурентном выполнении корутин.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from typing import Any

__all__ = ["CorrelationContext", "current_context", "log_context"]


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Идентификаторы текущего workflow.

    Все поля необязательны: на разных стадиях известна разная их часть.
    Секреты в контекст не помещаются — он целиком попадает в логи.
    """

    correlation_id: str | None = None
    scan_id: str | None = None
    v_id: str | None = None
    k_id: str | None = None
    request_id: str | None = None
    provider: str | None = None
    network: str | None = None
    operation: str | None = None

    def as_fields(self) -> dict[str, str]:
        """Непустые поля контекста для structured logging."""
        return {
            name: value
            for name, value in (
                ("correlation_id", self.correlation_id),
                ("scan_id", self.scan_id),
                ("v_id", self.v_id),
                ("k_id", self.k_id),
                ("request_id", self.request_id),
                ("provider", self.provider),
                ("network", self.network),
                ("operation", self.operation),
            )
            if value is not None
        }


#: Пустой контекст. Frozen dataclass, поэтому безопасно переиспользуется.
_EMPTY = CorrelationContext()

_CONTEXT: ContextVar[CorrelationContext | None] = ContextVar(
    "monik_correlation_context", default=None
)


def current_context() -> CorrelationContext:
    """Текущий контекст корреляции (пустой, если не установлен)."""
    return _CONTEXT.get() or _EMPTY


@contextmanager
def log_context(**fields: Any) -> Iterator[CorrelationContext]:
    """Временно дополнить контекст корреляции.

    Значения объединяются с текущим контекстом, а по выходу восстанавливается
    предыдущее состояние — в том числе при исключении.
    """
    known = {name for name in CorrelationContext.__dataclass_fields__}
    unknown = set(fields) - known
    if unknown:
        raise ValueError(f"unknown correlation fields: {', '.join(sorted(unknown))}")
    updates = {name: (None if value is None else str(value)) for name, value in fields.items()}
    updated = replace(current_context(), **updates)
    token: Token[CorrelationContext | None] = _CONTEXT.set(updated)
    try:
        yield updated
    finally:
        _CONTEXT.reset(token)
