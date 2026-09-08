"""Проверка допустимости URL перед запросом.

Monik не выполняет запросы по произвольным URL: даже если внешний API вернул
ссылку, обращаться по ней без явного разрешения нельзя
(``06_AGGREGATOR_ADAPTERS.md`` §80, ``32_SECURITY.md``).

Реализована защита от SSRF: разрешён только ``https``, хост обязан входить
в allowlist, обращения к loopback, приватным и link-local адресам
запрещены, userinfo в URL не допускается.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from monik.domain.errors import DomainValidationError

__all__ = ["UrlPolicy"]

#: Схемы, по которым разрешены внешние запросы.
_ALLOWED_SCHEMES = frozenset({"https"})


class UrlPolicy:
    """Allowlist хостов и правила безопасности URL."""

    def __init__(self, allowed_hosts: frozenset[str] | set[str] | tuple[str, ...]) -> None:
        self._allowed = frozenset(host.strip().lower() for host in allowed_hosts if host.strip())

    @property
    def allowed_hosts(self) -> frozenset[str]:
        """Разрешённые хосты."""
        return self._allowed

    def with_hosts(self, hosts: tuple[str, ...]) -> UrlPolicy:
        """Вернуть политику, дополненную хостами."""
        return UrlPolicy(self._allowed | {host.strip().lower() for host in hosts})

    def is_allowed(self, url: str) -> bool:
        """Разрешён ли URL."""
        try:
            self.validate(url)
        except DomainValidationError:
            return False
        return True

    def validate(self, url: str) -> str:
        """Проверить URL и вернуть нормализованный хост.

        Ошибка валидации является ошибкой данных, а не сетевым сбоем:
        повторять такой запрос бессмысленно.
        """
        parts = urlsplit(url)
        if parts.scheme.lower() not in _ALLOWED_SCHEMES:
            raise DomainValidationError(
                f"url scheme {parts.scheme!r} is not allowed; only https is permitted",
                code="url_scheme_forbidden",
            )
        if parts.username or parts.password:
            raise DomainValidationError(
                "url must not contain credentials", code="url_credentials_forbidden"
            )
        host = (parts.hostname or "").strip().lower()
        if not host:
            raise DomainValidationError("url has no host", code="url_host_missing")
        self._reject_special_addresses(host)
        if host not in self._allowed:
            raise DomainValidationError(
                f"host {host!r} is not in the allowed hosts list",
                code="url_host_not_allowed",
            )
        return host

    @staticmethod
    def _reject_special_addresses(host: str) -> None:
        """Отклонить обращения во внутреннюю сеть."""
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if host == "localhost" or host.endswith(".localhost"):
                raise DomainValidationError(
                    "loopback host is not allowed", code="url_host_forbidden"
                ) from None
            return
        if (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise DomainValidationError(
                f"address {host} points to a non-public network",
                code="url_host_forbidden",
            )
