"""Конфигурация HTTP-клиента."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection

__all__ = ["HttpConfig"]


class HttpConfig(ConfigSection):
    """Ограничения и политика безопасности внешних HTTP-запросов.

    Соответствует ``38_INTERFACES.md`` §36-37 и ``32_SECURITY.md``:
    обязательны timeout, проверка TLS, лимит размера ответа и контролируемая
    политика редиректов.
    """

    connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    read_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    max_response_bytes: int = Field(default=4 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    max_connections: int = Field(default=32, ge=1, le=512)
    verify_tls: bool = True
    follow_redirects: bool = False
    max_redirects: int = Field(default=0, ge=0, le=5)
    user_agent: str = Field(default="monik/0.1", min_length=1, max_length=128)
    extra_allowed_hosts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Проверку TLS отключить нельзя.

        Соответствует ``06_AGGREGATOR_ADAPTERS.md`` §79: для production
        отключение TLS verification запрещено.
        """
        if not self.verify_tls:
            raise ValueError("verify_tls must remain true: TLS verification is mandatory")
        if not self.follow_redirects and self.max_redirects:
            raise ValueError("max_redirects requires follow_redirects to be enabled")
        for host in self.extra_allowed_hosts:
            if not host or host != host.strip().lower():
                raise ValueError(f"allowed host must be a normalized lowercase name: {host!r}")
        return self
