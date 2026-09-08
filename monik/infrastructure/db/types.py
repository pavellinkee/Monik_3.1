"""Преобразование доменных значений в представление SQLite и обратно.

Правила хранения (``30_DATABASE_SCHEMA.md`` §10, §56-58,
``09_PROFIT_CALCULATOR.md`` §3-4):

* ``Decimal`` хранится как ``TEXT`` — это сохраняет точность; ``REAL``
  (binary float) для финансовых значений запрещён;
* raw blockchain amount хранится как ``TEXT``, а не ``INTEGER``: значение
  токена с 18 decimals легко превышает диапазон 64-битного целого SQLite
  (например 1000 токенов = 10^21 > 9.22·10^18);
* timestamps хранятся как ISO-8601 в UTC — такой формат лексикографически
  сортируется и не зависит от локальной timezone VPS;
* ``bool`` хранится как ``0``/``1``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from monik.domain.value_objects.timestamps import ensure_utc

__all__ = [
    "from_bool",
    "from_decimal",
    "from_json",
    "from_raw_amount",
    "from_timestamp",
    "to_bool",
    "to_decimal",
    "to_json",
    "to_raw_amount",
    "to_timestamp",
]


def to_timestamp(moment: datetime) -> str:
    """Сериализовать timezone-aware момент в ISO-8601 UTC."""
    return ensure_utc(moment).isoformat()


def from_timestamp(value: str) -> datetime:
    """Разобрать сохранённый timestamp."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"stored timestamp is not timezone-aware: {value!r}")
    return parsed.astimezone(UTC)


def to_decimal(value: Decimal) -> str:
    """Сериализовать точное числовое значение."""
    if isinstance(value, float):  # pragma: no cover - защита от нетипизированного ввода
        raise TypeError("float must never be stored as a financial value")
    return str(value)


def from_decimal(value: str) -> Decimal:
    """Разобрать точное числовое значение."""
    return Decimal(value)


def to_raw_amount(value: int) -> str:
    """Сериализовать raw blockchain amount."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"raw amount must be int, got {type(value).__name__}")
    return str(value)


def from_raw_amount(value: str) -> int:
    """Разобрать raw blockchain amount."""
    return int(value)


def to_bool(value: bool) -> int:
    """Сериализовать булево значение."""
    return 1 if value else 0


def from_bool(value: int) -> bool:
    """Разобрать булево значение."""
    return bool(value)


def to_json(value: Any) -> str:
    """Сериализовать вспомогательную структуру.

    Используется для route snapshot, scan scope и подобных структур, у которых
    нет отдельных колонок. Сортировка ключей делает представление
    детерминированным (``36_DATA_MODELS.md`` §77).
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def from_json(value: str) -> Any:
    """Разобрать вспомогательную структуру."""
    return json.loads(value)
