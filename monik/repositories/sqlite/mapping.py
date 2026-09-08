"""Преобразование доменных моделей в строки таблиц и обратно.

Repository выполняет mapping между domain и database models
(``30_DATABASE_SCHEMA.md`` §5, §7). Доменные модели не знают о SQLite.
"""

from __future__ import annotations

from typing import Any

import aiosqlite
from pydantic import ValidationError

from monik.domain.errors import DatabaseError
from monik.domain.models.base import DomainModel
from monik.infrastructure.db.types import from_json, to_json

__all__ = ["column", "dump_model", "load_model", "optional_column"]


def dump_model(model: DomainModel | None) -> str | None:
    """Сериализовать доменную модель в JSON-колонку."""
    if model is None:
        return None
    return to_json(model.model_dump(mode="json"))


def load_model[T: DomainModel](model_type: type[T], value: Any) -> T:
    """Восстановить доменную модель из JSON-колонки.

    Несовместимые данные — ошибка persistence, а не «почти валидная» модель:
    повреждённая запись не должна превращаться в рабочий доменный объект.
    """
    if value is None:
        raise DatabaseError(
            f"stored {model_type.__name__} is missing",
            code="database_row_incomplete",
        )
    try:
        return model_type.model_validate(from_json(str(value)))
    except (ValidationError, ValueError) as exc:
        raise DatabaseError(
            f"stored {model_type.__name__} is not valid: {exc}",
            code="database_row_invalid",
        ) from exc


def column(row: aiosqlite.Row, name: str) -> Any:
    """Прочитать обязательную колонку."""
    value = row[name]
    if value is None:
        raise DatabaseError(
            f"column {name} is unexpectedly NULL",
            code="database_row_incomplete",
        )
    return value


def optional_column(row: aiosqlite.Row, name: str) -> Any:
    """Прочитать необязательную колонку."""
    return row[name]
