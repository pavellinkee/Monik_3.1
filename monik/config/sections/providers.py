"""Конфигурация aggregator providers."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.config.secrets import SecretRef
from monik.domain.enums.providers import ProviderId
from monik.domain.value_objects.identity import NetworkId

__all__ = ["ProviderConfig"]


class ProviderConfig(ConfigSection):
    """Параметры одного провайдера (``17_CONFIGURATION.md`` §25-27).

    Credentials задаются только ссылкой на environment
    (``17_CONFIGURATION.md`` §26): реальный ключ в repository не попадает.
    Disabled provider не получает запросов (``17_CONFIGURATION.md`` §27).
    """

    provider_id: ProviderId
    enabled: bool = False
    base_url: str | None = Field(default=None, max_length=512)
    api_key: SecretRef | None = None
    supported_networks: tuple[NetworkId, ...] = ()
    request_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    max_concurrent_requests: int = Field(default=4, ge=1, le=128)
    requests_per_second: float = Field(default=5.0, gt=0, le=1000)
    allow_same_provider_round_trip: bool = False

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.base_url is not None and not self.base_url.startswith("https://"):
            raise ValueError("provider base_url must use https")
        if self.enabled and not self.supported_networks:
            raise ValueError(
                f"provider {self.provider_id.value} is enabled but declares no supported networks"
            )
        return self
