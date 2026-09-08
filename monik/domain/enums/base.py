"""Базовый класс для стабильных доменных enum'ов.

Значения enum'ов попадают в persistent state, поэтому должны быть стабильными
строками (``36_DATA_MODELS.md`` §76, ``21_API_CONTRACTS.md`` §67).
Переименование значения = breaking change, требующий migration.
"""

from __future__ import annotations

from enum import StrEnum


class DomainEnum(StrEnum):
    """Строковый enum со стабильным значением.

    Наследование от :class:`~enum.StrEnum` даёт детерминированную сериализацию
    и позволяет хранить значение в БД как обычную строку.
    """

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"
