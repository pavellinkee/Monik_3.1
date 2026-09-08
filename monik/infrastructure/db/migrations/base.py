"""Описание миграции схемы."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Migration"]


@dataclass(frozen=True, slots=True)
class Migration:
    """Одна миграция схемы.

    Каждая миграция имеет уникальную возрастающую версию и применяется
    целиком в одной транзакции (``30_DATABASE_SCHEMA.md`` §15-17).
    """

    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("migration version must be positive")
        if not self.name:
            raise ValueError("migration must have a name")
        if not self.statements:
            raise ValueError(f"migration {self.version} has no statements")
