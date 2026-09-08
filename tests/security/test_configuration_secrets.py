"""Security-тесты конфигурации: секреты не раскрываются в диагностике и ошибках."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from monik.config import configuration_diagnostics, parse_configuration
from monik.domain.errors import ConfigurationError
from monik.services.observability.redaction import REDACTED, SecretRegistry
from tests.unit.config.conftest import USDT_ADDRESS, base_document

ONEINCH_SECRET = "oneinch-live-key-4f8a7b6c5d4e3f2a"
ZEROX_SECRET = "zerox-live-key-9d8e7f6a5b4c3d2e"
BOT_TOKEN = "8123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
CHAT_ID = "-1001234567890"

ENV = {
    "MONIK_ONEINCH_API_KEY": ONEINCH_SECRET,
    "MONIK_ZEROX_API_KEY": ZEROX_SECRET,
    "MONIK_TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "MONIK_TELEGRAM_CHAT_ID": CHAT_ID,
}

ALL_SECRETS = (ONEINCH_SECRET, ZEROX_SECRET, BOT_TOKEN)


@pytest.fixture
def document() -> dict[str, Any]:
    doc = base_document()
    doc["notifications"] = {
        "enabled": True,
        "telegram": {
            "enabled": True,
            "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
            "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
        },
    }
    return doc


def test_diagnostics_never_expose_secret_values(document: dict[str, Any]) -> None:
    """Diagnostics показывают имена переменных, но не значения (17 §57-58)."""
    loaded = parse_configuration(document, environ=ENV, registry=SecretRegistry())
    rendered = json.dumps(configuration_diagnostics(loaded), ensure_ascii=False)
    for secret in ALL_SECRETS:
        assert secret not in rendered
    assert "MONIK_TELEGRAM_BOT_TOKEN" in rendered


def test_diagnostics_report_useful_state(document: dict[str, Any]) -> None:
    loaded = parse_configuration(document, environ=ENV, registry=SecretRegistry())
    diagnostics = configuration_diagnostics(loaded)
    assert diagnostics["environment"] == "development"
    assert diagnostics["providers"] == ["oneinch", "zero_x"]
    assert diagnostics["networks"] == ["polygon"]
    assert diagnostics["resolved_env_references"] == 4
    assert diagnostics["level2"]["max_parallel"] == 20


def test_validation_error_message_does_not_expose_secrets(
    document: dict[str, Any],
) -> None:
    """Секрет не должен попадать в текст ошибки (17 §61)."""
    document["scanner"]["base_token_address"] = ONEINCH_SECRET
    registry = SecretRegistry()
    registry.register(ONEINCH_SECRET)
    with pytest.raises(ConfigurationError) as error:
        parse_configuration(document, environ=ENV, registry=registry)
    assert ONEINCH_SECRET not in str(error.value)


def test_configuration_model_contains_no_secret_values(document: dict[str, Any]) -> None:
    loaded = parse_configuration(document, environ=ENV, registry=SecretRegistry())
    serialized = loaded.config.model_dump_json()
    for secret in ALL_SECRETS:
        assert secret not in serialized


def test_secret_store_repr_lists_names_only(document: dict[str, Any]) -> None:
    loaded = parse_configuration(document, environ=ENV, registry=SecretRegistry())
    rendered = repr(loaded.secrets)
    for secret in ALL_SECRETS:
        assert secret not in rendered


def test_example_config_has_no_literal_secrets(repo_root: Any) -> None:
    """В репозитории не должно быть реальных значений (CLAUDE.md §49)."""
    text = (repo_root / "config" / "config.example.yaml").read_text(encoding="utf-8")
    assert "env:" in text
    for marker in ('bot_token: "', 'api_key: "', 'chat_id: "'):
        assert marker not in text


def test_diagnostics_redact_secret_leaked_into_plain_field(
    document: dict[str, Any],
) -> None:
    """Даже если секрет попал в обычное поле, диагностика его скрывает."""
    document["networks"][0]["name"] = f"Polygon {ONEINCH_SECRET}"
    registry = SecretRegistry()
    loaded = parse_configuration(document, environ=ENV, registry=registry)
    rendered = json.dumps(configuration_diagnostics(loaded), ensure_ascii=False)
    assert ONEINCH_SECRET not in rendered
    assert loaded.config.scanner.base_token_address == USDT_ADDRESS.lower()
    assert REDACTED not in loaded.config.version


def test_tests_never_target_production_database_path(repo_root: Any) -> None:
    """Тесты используют только временные базы (30 §91-92)."""
    forbidden = ("data/" + "monik.db", "/var/lib/" + "monik")
    this_file = pathlib.Path(__file__).resolve()
    for path in (repo_root / "tests").rglob("*.py"):
        if path.resolve() == this_file:
            continue
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{path.name} references production database {marker}"
