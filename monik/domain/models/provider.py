"""Модель внешнего aggregator provider."""

from __future__ import annotations

from pydantic import Field

from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel

__all__ = ["Provider"]


class Provider(DomainModel):
    """Aggregator provider (``36_DATA_MODELS.md`` §14).

    Credentials частью доменной модели не являются (``36_DATA_MODELS.md`` §68).
    Модель также не утверждает, что provider поддерживает операцию: это
    определяет Capability Registry (``36_DATA_MODELS.md`` §15).
    """

    provider_id: ProviderId
    name: str = Field(min_length=1, max_length=64)
    enabled: bool = True
