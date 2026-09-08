"""Базовый класс canonical domain models.

Все доменные модели immutable: изменение состояния выполняется созданием новой
модели через соответствующий domain/application service, а не присваиванием
поля (``35_STATE_MACHINES.md`` §4, ``36_DATA_MODELS.md`` §74).

``extra="forbid"`` защищает от протечки provider-specific полей в domain layer
(``36_DATA_MODELS.md`` §99.12).
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict

__all__ = ["DomainModel"]


class DomainModel(BaseModel):
    """Frozen pydantic-модель с запретом неизвестных полей."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=False,
    )

    def replace(self, **changes: Any) -> Self:
        """Вернуть копию модели с изменёнными полями.

        Валидация выполняется повторно, поэтому нарушить инварианты модели
        через ``replace`` нельзя.
        """
        return type(self).model_validate({**self.model_dump(), **changes})
