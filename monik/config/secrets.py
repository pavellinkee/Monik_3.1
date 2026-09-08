"""Секрет-ссылки и их разрешение из environment.

Секреты никогда не хранятся в configuration file
(``17_CONFIGURATION.md`` §5, ``22_SECURITY.md``): в YAML указывается только
ссылка ``{env: "MONIK_..."}``, а значение приходит из environment.

Configuration subsystem — **единственное** место, которому разрешено читать
``os.environ`` (``25_PROJECT_STRUCTURE.md`` §64).
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

from monik.domain.errors import ConfigurationError
from monik.services.observability.redaction import REDACTED, SecretRegistry

__all__ = ["SecretRef", "SecretResolver", "SecretStore", "SecretValue"]


class SecretRef(BaseModel):
    """Ссылка на секрет в environment.

    В YAML записывается как ``api_key: { env: "MONIK_ONEINCH_API_KEY" }``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    env: str = Field(min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$")


class SecretValue:
    """Разрешённое значение секрета.

    Значение недоступно через ``repr``/``str``, поэтому случайная
    интерполяция в сообщение или лог не раскрывает его. Получить исходную
    строку можно только явным вызовом :meth:`get`.
    """

    __slots__ = ("_env_name", "_value")

    def __init__(self, env_name: str, value: str) -> None:
        self._env_name = env_name
        self._value = value

    @property
    def env_name(self) -> str:
        """Имя переменной окружения, из которой получено значение."""
        return self._env_name

    def get(self) -> str:
        """Вернуть значение секрета.

        Вызывается только на границе с внешней системой (заголовок запроса,
        Telegram API) и никогда не попадает в логи или диагностику.
        """
        return self._value

    def __repr__(self) -> str:
        return f"SecretValue(env={self._env_name!r}, value={REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretValue):
            return NotImplemented
        return self._env_name == other._env_name and self._value == other._value

    def __hash__(self) -> int:
        return hash((self._env_name, self._value))


class SecretResolver:
    """Разрешает :class:`SecretRef` в :class:`SecretValue`.

    Каждое найденное значение регистрируется в :class:`SecretRegistry`,
    поэтому далее оно автоматически вычёркивается из любых логов.
    """

    def __init__(
        self,
        environ: dict[str, str] | None = None,
        *,
        registry: SecretRegistry | None = None,
    ) -> None:
        self._environ = dict(os.environ) if environ is None else dict(environ)
        self._registry = registry

    def resolve(self, ref: SecretRef, *, context: str) -> SecretValue:
        """Разрешить ссылку.

        Отсутствующая или пустая переменная — ошибка конфигурации:
        подставлять пустое значение и запускаться с ним запрещено
        (``17_CONFIGURATION.md`` §11).
        """
        raw = self._environ.get(ref.env)
        if raw is None or not raw.strip():
            raise ConfigurationError(
                f"{context}: environment variable {ref.env} is not set or empty",
                code="secret_missing",
            )
        value = raw.strip()
        if self._registry is not None:
            self._registry.register(value)
        return SecretValue(ref.env, value)

    def is_available(self, ref: SecretRef) -> bool:
        """Задана ли переменная окружения для ссылки."""
        raw = self._environ.get(ref.env)
        return bool(raw and raw.strip())


class SecretStore:
    """Разрешённые секреты приложения.

    Хранится отдельно от схемы конфигурации, поэтому сериализация и
    fingerprint конфигурации физически не могут содержать секрет
    (``30_DATABASE_SCHEMA.md`` §58, ``17_CONFIGURATION.md`` §57).
    """

    __slots__ = ("_values",)

    def __init__(self, values: dict[str, SecretValue] | None = None) -> None:
        self._values = dict(values or {})

    def add(self, secret: SecretValue) -> None:
        """Добавить разрешённый секрет."""
        self._values[secret.env_name] = secret

    def get(self, ref: SecretRef) -> SecretValue:
        """Вернуть значение по ссылке."""
        secret = self._values.get(ref.env)
        if secret is None:
            raise ConfigurationError(
                f"secret {ref.env} was not resolved during configuration loading",
                code="secret_unresolved",
            )
        return secret

    def has(self, ref: SecretRef) -> bool:
        """Разрешён ли секрет по этой ссылке."""
        return ref.env in self._values

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"SecretStore(resolved={sorted(self._values)})"
