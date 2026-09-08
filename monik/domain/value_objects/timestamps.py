"""Timezone-aware временные метки.

Все timestamps используют UTC (``36_DATA_MODELS.md`` §5,
``30_DATABASE_SCHEMA.md`` §10-12). Naive datetime отклоняется: он зависит от
локального timezone машины и делает поведение недетерминированным.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BeforeValidator

__all__ = ["UtcDatetime", "ensure_utc"]


def ensure_utc(value: datetime) -> datetime:
    """Привести timezone-aware datetime к UTC.

    Naive datetime не принимается: неизвестно, в какой зоне он задан.
    """
    if value.tzinfo is None:
        raise ValueError("naive datetime is not allowed; timestamps must be timezone-aware UTC")
    return value.astimezone(UTC)


def _validate(value: Any) -> Any:
    if isinstance(value, datetime):
        return ensure_utc(value)
    return value


#: ``datetime``, гарантированно timezone-aware и приведённый к UTC.
UtcDatetime = Annotated[datetime, BeforeValidator(_validate)]
