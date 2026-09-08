"""Configuration subsystem.

Единственный authoritative источник пользовательских настроек
(``17_CONFIGURATION.md`` §1). Business logic не читает YAML, ``.env`` или
``os.environ`` самостоятельно (``25_PROJECT_STRUCTURE.md`` §64) — она
получает уже валидированный объект :class:`Configuration`.
"""

from monik.config.base import ConfigSection
from monik.config.diagnostics import configuration_diagnostics
from monik.config.loader import (
    ENV_PREFIX,
    LoadedConfiguration,
    load_configuration,
    parse_configuration,
)
from monik.config.root import Configuration
from monik.config.secrets import SecretRef, SecretResolver, SecretStore, SecretValue

__all__ = [
    "ENV_PREFIX",
    "ConfigSection",
    "Configuration",
    "LoadedConfiguration",
    "SecretRef",
    "SecretResolver",
    "SecretStore",
    "SecretValue",
    "configuration_diagnostics",
    "load_configuration",
    "parse_configuration",
]
