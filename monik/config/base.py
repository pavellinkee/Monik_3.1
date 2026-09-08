"""Базовый класс секций конфигурации."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["ConfigSection"]


class ConfigSection(BaseModel):
    """Immutable секция валидированной конфигурации.

    ``extra="forbid"`` превращает опечатку в явную ошибку конфигурации,
    а не в молча проигнорированный параметр (``17_CONFIGURATION.md`` §11).
    После загрузки объект неизменяем (``17_CONFIGURATION.md`` §50-51).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )
