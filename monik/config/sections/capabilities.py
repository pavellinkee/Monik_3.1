"""Конфигурация Capability Registry."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection

__all__ = ["CapabilityConfig"]


class CapabilityConfig(ConfigSection):
    """Параметры обнаружения и обновления capability.

    Discovery выполняется при старте и по расписанию, а не перед каждым scan
    (``08_CAPABILITY_REGISTRY.md`` §3-4). Временная ошибка не переводит
    комбинацию в ``UNSUPPORTED`` немедленно: для этого нужен порог
    (``20_CAPABILITY_REGISTRY.md`` §26-28).
    """

    enabled: bool = True
    refresh_on_startup: bool = True
    refresh_interval_hours: int = Field(default=24, ge=1, le=8760)
    freshness_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    failure_threshold: int = Field(default=3, ge=1, le=100)
    recovery_threshold: int = Field(default=2, ge=1, le=100)
    treat_unknown_as_supported: bool = False

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """``UNKNOWN`` не может трактоваться как ``SUPPORTED``.

        Соответствует ``36_DATA_MODELS.md`` §61 и
        ``08_CAPABILITY_REGISTRY.md`` §10.
        """
        if self.treat_unknown_as_supported:
            raise ValueError(
                "treat_unknown_as_supported must remain false: UNKNOWN capability "
                "is not proof of support"
            )
        return self
