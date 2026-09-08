"""Базовый класс для валидируемых строковых value objects.

Наследники являются подклассами ``str``: они сериализуются как обычные строки
(в БД, логи, Telegram), но сохраняют различимость типов для mypy и выполняют
нормализацию в одном месте.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

__all__ = ["ValidatedStr"]


class ValidatedStr(str):
    """Строка с обязательной валидацией и нормализацией.

    Наследник обязан реализовать :meth:`normalize`. Конструктор всегда
    возвращает нормализованное значение, поэтому сравнение и хеширование
    двух логически одинаковых значений даёт одинаковый результат.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> Self:
        if not isinstance(value, str):  # pragma: no cover - защита от нетипизированного ввода
            raise TypeError(f"{cls.__name__} expects str, got {type(value).__name__}")
        return super().__new__(cls, cls.normalize(value))

    @classmethod
    def normalize(cls, value: str) -> str:
        """Проверить и нормализовать сырое значение."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str.__repr__(self)})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Позволяет использовать тип как поле pydantic-модели."""
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, return_schema=core_schema.str_schema(), when_used="json"
            ),
        )
