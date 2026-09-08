"""Тесты разрешения секретов и их защиты."""

from __future__ import annotations

from typing import Any

import pytest

from monik.config import parse_configuration
from monik.config.secrets import SecretRef, SecretResolver, SecretStore
from monik.domain.errors import ConfigurationError
from monik.services.observability.redaction import REDACTED, SecretRegistry

SECRET = "oneinch-example-key-value"


class TestSecretResolver:
    def test_resolves_from_environment(self) -> None:
        resolver = SecretResolver({"MONIK_X": SECRET})
        value = resolver.resolve(SecretRef(env="MONIK_X"), context="test")
        assert value.get() == SECRET
        assert value.env_name == "MONIK_X"

    def test_missing_variable_is_configuration_error(self) -> None:
        """Пустой секрет не подставляется молча (17 §11)."""
        resolver = SecretResolver({})
        with pytest.raises(ConfigurationError, match="not set or empty"):
            resolver.resolve(SecretRef(env="MONIK_X"), context="test")

    def test_blank_variable_is_configuration_error(self) -> None:
        resolver = SecretResolver({"MONIK_X": "   "})
        with pytest.raises(ConfigurationError, match="not set or empty"):
            resolver.resolve(SecretRef(env="MONIK_X"), context="test")

    def test_registers_value_for_redaction(self) -> None:
        registry = SecretRegistry()
        SecretResolver({"MONIK_X": SECRET}, registry=registry).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        assert len(registry) == 1
        assert SECRET not in registry.scrub(f"key {SECRET}")

    def test_reference_name_must_be_upper_snake(self) -> None:
        with pytest.raises(ValueError, match="pattern"):
            SecretRef(env="lowercase")


class TestSecretValueDoesNotLeak:
    def test_repr_hides_value(self) -> None:
        value = SecretResolver({"MONIK_X": SECRET}).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        assert SECRET not in repr(value)
        assert REDACTED in repr(value)

    def test_str_hides_value(self) -> None:
        value = SecretResolver({"MONIK_X": SECRET}).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        assert str(value) == REDACTED

    def test_format_hides_value(self) -> None:
        value = SecretResolver({"MONIK_X": SECRET}).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        assert SECRET not in f"token is {value}"


class TestSecretStore:
    def test_stores_and_returns_secret(self) -> None:
        value = SecretResolver({"MONIK_X": SECRET}).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        store = SecretStore()
        store.add(value)
        assert store.get(SecretRef(env="MONIK_X")).get() == SECRET

    def test_unresolved_reference_is_reported(self) -> None:
        with pytest.raises(ConfigurationError, match="was not resolved"):
            SecretStore().get(SecretRef(env="MONIK_X"))

    def test_repr_lists_names_only(self) -> None:
        value = SecretResolver({"MONIK_X": SECRET}).resolve(
            SecretRef(env="MONIK_X"), context="test"
        )
        store = SecretStore()
        store.add(value)
        assert SECRET not in repr(store)
        assert "MONIK_X" in repr(store)


class TestConfigurationSecretHandling:
    def test_enabled_provider_without_secret_stops_startup(self, document: dict[str, Any]) -> None:
        with pytest.raises(ConfigurationError, match="MONIK_ONEINCH_API_KEY"):
            parse_configuration(document, environ={})

    def test_disabled_provider_secret_is_not_required(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        document["providers"].append(
            {
                "provider_id": "velora",
                "enabled": False,
                "api_key": {"env": "MONIK_VELORA_API_KEY"},
                "supported_networks": ["polygon"],
            }
        )
        loaded = parse_configuration(document, environ=env)
        assert len(loaded.secrets) == 2

    def test_telegram_secrets_are_required_when_enabled(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        document["notifications"] = {
            "enabled": True,
            "telegram": {
                "enabled": True,
                "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
                "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
            },
        }
        with pytest.raises(ConfigurationError, match="MONIK_TELEGRAM_BOT_TOKEN"):
            parse_configuration(document, environ=env)

    def test_telegram_enabled_without_reference_is_rejected(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        document["notifications"] = {"enabled": True, "telegram": {"enabled": True}}
        with pytest.raises(ConfigurationError, match="bot_token"):
            parse_configuration(document, environ=env)

    def test_secret_never_appears_in_configuration_dump(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        """Секрет физически не входит в модель конфигурации."""
        loaded = parse_configuration(document, environ=env)
        dumped = loaded.config.model_dump_json()
        assert SECRET not in dumped
        assert "MONIK_ONEINCH_API_KEY" in dumped

    def test_secret_never_appears_in_version_fingerprint(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        loaded = parse_configuration(document, environ=env)
        assert SECRET not in loaded.config.version

    def test_secret_never_appears_in_repr(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        loaded = parse_configuration(document, environ=env)
        assert SECRET not in repr(loaded)
