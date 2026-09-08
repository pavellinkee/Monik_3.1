"""Загрузка, нормализация и валидация конфигурации.

Порядок загрузки (``17_CONFIGURATION.md`` §9):

1. определить источник;
2. загрузить configuration file;
3. применить разрешённые environment overrides;
4. применить defaults;
5. выполнить validation;
6. создать immutable configuration object;
7. передать конфигурацию остальным подсистемам.

Приоритет источников явно определён (``17_CONFIGURATION.md`` §59):
``environment override`` > ``configuration file`` > ``safe default``.
"""

from __future__ import annotations

import os
import pathlib
from decimal import Decimal, InvalidOperation
from typing import Any

import yaml
from pydantic import ValidationError

from monik.config.root import Configuration
from monik.config.secrets import SecretRef, SecretResolver, SecretStore
from monik.domain.errors import ConfigurationError
from monik.services.observability.redaction import SecretRegistry, redact_text

__all__ = ["ENV_PREFIX", "LoadedConfiguration", "load_configuration", "parse_configuration"]

#: Префикс переменных окружения, переопределяющих конфигурацию.
#: Путь внутри документа разделяется двойным подчёркиванием:
#: ``MONIK__SCANNER__LEVEL1__INTERVAL_SECONDS=60``.
ENV_PREFIX = "MONIK__"

_LIST_SEPARATOR = ","
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class LoadedConfiguration:
    """Результат загрузки: валидированная конфигурация и её секреты.

    Секреты намеренно вынесены из модели конфигурации, поэтому её дамп и
    отпечаток не могут их содержать.
    """

    __slots__ = ("config", "secrets", "source")

    def __init__(
        self,
        config: Configuration,
        secrets: SecretStore,
        source: str,
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.source = source

    def __repr__(self) -> str:
        return (
            f"LoadedConfiguration(source={self.source!r}, "
            f"version={self.config.version[:12]!r}, secrets={len(self.secrets)})"
        )


def _read_yaml(path: pathlib.Path) -> dict[str, Any]:
    """Прочитать YAML-документ конфигурации."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"cannot read configuration file {path}: {exc.strerror}",
            code="configuration_unreadable",
        ) from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"configuration file {path} is not valid YAML: {redact_text(str(exc))}",
            code="configuration_malformed",
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(
            f"configuration file {path} must contain a mapping at the top level",
            code="configuration_malformed",
        )
    return data


def _coerce_scalar(value: str) -> Any:
    """Привести строковое значение переменной окружения к типу документа.

    Числа с точкой остаются строками: они могут быть финансовыми значениями,
    а их преобразование в ``float`` запрещено (``17_CONFIGURATION.md`` §20).
    Pydantic сам приведёт строку к ``Decimal`` там, где это требуется.
    """
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if _LIST_SEPARATOR in stripped:
        return [_coerce_scalar(item) for item in stripped.split(_LIST_SEPARATOR)]
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    try:
        Decimal(stripped)
    except InvalidOperation:
        return stripped
    return stripped


def _apply_env_overrides(document: dict[str, Any], environ: dict[str, str]) -> list[str]:
    """Применить переопределения из environment.

    Возвращает список применённых путей для диагностики. Скрытых
    переопределений не существует (``17_CONFIGURATION.md`` §60): все они
    приходят только через переменные с префиксом ``MONIK__``.
    """
    applied: list[str] = []
    for name in sorted(environ):
        if not name.startswith(ENV_PREFIX):
            continue
        path = [part.lower() for part in name[len(ENV_PREFIX) :].split("__") if part]
        if not path:
            raise ConfigurationError(
                f"environment override {name} does not define a configuration path",
                code="configuration_override_invalid",
            )
        target: dict[str, Any] = document
        for key in path[:-1]:
            existing = target.get(key)
            if existing is None:
                existing = {}
                target[key] = existing
            elif not isinstance(existing, dict):
                raise ConfigurationError(
                    f"environment override {name} cannot descend into non-mapping "
                    f"configuration value at {'.'.join(path[:-1])}",
                    code="configuration_override_invalid",
                )
            target = existing
        target[path[-1]] = _coerce_scalar(environ[name])
        applied.append(".".join(path))
    return applied


def _collect_secret_refs(config: Configuration) -> list[tuple[SecretRef, str]]:
    """Собрать все секрет-ссылки активной конфигурации с их контекстом."""
    refs: list[tuple[SecretRef, str]] = []
    for provider in config.enabled_providers:
        if provider.api_key is not None:
            refs.append((provider.api_key, f"provider {provider.provider_id.value} api_key"))
    telegram = config.notifications.telegram
    if telegram.enabled:
        if telegram.bot_token is not None:
            refs.append((telegram.bot_token, "telegram bot_token"))
        if telegram.chat_id is not None:
            refs.append((telegram.chat_id, "telegram chat_id"))
    return refs


def parse_configuration(
    document: dict[str, Any],
    *,
    environ: dict[str, str] | None = None,
    registry: SecretRegistry | None = None,
    source: str = "<memory>",
) -> LoadedConfiguration:
    """Провалидировать документ конфигурации и разрешить его секреты.

    Невалидная конфигурация приводит к :class:`ConfigurationError`
    и не заменяется «безопасными на вид» значениями
    (``17_CONFIGURATION.md`` §11).
    """
    env = dict(os.environ) if environ is None else dict(environ)
    merged = dict(document)
    _apply_env_overrides(merged, env)

    try:
        config = Configuration.model_validate(merged)
    except ValidationError as exc:
        raise ConfigurationError(
            f"invalid configuration from {source}: "
            f"{_format_validation_error(exc, registry=registry)}",
            code="configuration_invalid",
        ) from exc

    resolver = SecretResolver(env, registry=registry)
    store = SecretStore()
    for ref, context in _collect_secret_refs(config):
        store.add(resolver.resolve(ref, context=context))

    return LoadedConfiguration(config=config, secrets=store, source=source)


def load_configuration(
    path: str | pathlib.Path,
    *,
    environ: dict[str, str] | None = None,
    registry: SecretRegistry | None = None,
) -> LoadedConfiguration:
    """Загрузить конфигурацию из файла."""
    config_path = pathlib.Path(path)
    if not config_path.is_file():
        raise ConfigurationError(
            f"configuration file not found: {config_path}",
            code="configuration_missing",
        )
    document = _read_yaml(config_path)
    return parse_configuration(
        document,
        environ=environ,
        registry=registry,
        source=str(config_path),
    )


def _format_validation_error(
    error: ValidationError,
    *,
    registry: SecretRegistry | None = None,
) -> str:
    """Составить понятное сообщение об ошибке валидации.

    Сообщение содержит путь параметра и причину
    (``17_CONFIGURATION.md`` §61) и проходит через редакцию, чтобы значение
    секрета не попало в текст ошибки.
    """
    parts: list[str] = []
    for item in error.errors():
        location = ".".join(str(piece) for piece in item["loc"]) or "<root>"
        parts.append(f"{location}: {item['msg']}")
    return redact_text("; ".join(parts), registry=registry)
