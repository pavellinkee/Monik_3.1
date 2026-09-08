"""Security regression: секрет не появляется ни на одном уровне вывода.

``28_OBSERVABILITY.md`` §14-19, §43 и ``CLAUDE.md`` §48-49: bot token,
API-ключи и заголовки авторизации не должны попадать в логи, метрики,
исключения и диагностику конфигурации.
"""

from __future__ import annotations

import json
import logging

import pytest

from monik.config import configuration_diagnostics, parse_configuration
from monik.services.observability import (
    REDACTED,
    MetricsRegistry,
    SecretRegistry,
    StructuredFormatter,
    log_context,
    log_fields,
    names,
    redact_mapping,
    redact_text,
)
from tests.unit.config.conftest import base_document

ONEINCH_SECRET = "oneinch-live-key-4f8a7b6c5d4e3f2a"
ZEROX_SECRET = "zerox-live-key-9d8e7f6a5b4c3d2e"
BOT_TOKEN = "8123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"

ENV = {
    "MONIK_ONEINCH_API_KEY": ONEINCH_SECRET,
    "MONIK_ZEROX_API_KEY": ZEROX_SECRET,
    "MONIK_TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "MONIK_TELEGRAM_CHAT_ID": "-1001234567890",
}

SECRETS = (ONEINCH_SECRET, ZEROX_SECRET, BOT_TOKEN)


@pytest.fixture
def registry() -> SecretRegistry:
    instance = SecretRegistry()
    for secret in SECRETS:
        instance.register(secret)
    return instance


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_is_redacted_in_message(registry: SecretRegistry, secret: str) -> None:
    formatter = StructuredFormatter(registry=registry)
    record = logging.LogRecord(
        name="monik.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"request failed with credentials {secret}",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert secret not in rendered
    assert REDACTED in rendered


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_is_redacted_in_structured_field(registry: SecretRegistry, secret: str) -> None:
    formatter = StructuredFormatter(registry=registry)
    record = logging.LogRecord(
        name="monik.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="provider call",
        args=(),
        exc_info=None,
    )
    record.__dict__.update(log_fields(authorization=f"Bearer {secret}"))

    rendered = formatter.format(record)

    assert secret not in rendered


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_is_redacted_in_exception_text(registry: SecretRegistry, secret: str) -> None:
    formatter = StructuredFormatter(registry=registry)
    try:
        raise RuntimeError(f"failed with {secret}")
    except RuntimeError:
        record = logging.LogRecord(
            name="monik.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="unexpected failure",
            args=(),
            exc_info=None,
        )
        record.exc_text = f"RuntimeError: failed with {secret}"

    rendered = formatter.format(record)

    assert secret not in rendered


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_is_redacted_in_correlation_context(registry: SecretRegistry, secret: str) -> None:
    """Контекст корреляции целиком попадает в логи (``28`` §19)."""
    formatter = StructuredFormatter(registry=registry)
    with log_context(request_id=secret):
        record = logging.LogRecord(
            name="monik.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="call",
            args=(),
            exc_info=None,
        )
        rendered = formatter.format(record)

    assert secret not in rendered


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_cannot_reach_metrics(registry: SecretRegistry, secret: str) -> None:
    """Метрики не принимают секрет как значение label (``28`` §43)."""
    metrics = MetricsRegistry(secrets=registry)

    with pytest.raises(ValueError, match="secret"):
        metrics.increment(names.LEVEL1_QUOTE_REQUESTS, provider=secret)


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_is_redacted_in_plain_helpers(registry: SecretRegistry, secret: str) -> None:
    assert secret not in redact_text(f"token={secret}", registry=registry)
    scrubbed = redact_mapping({"api_key": secret, "note": secret}, registry=registry)
    assert secret not in json.dumps(scrubbed)


def test_configuration_diagnostics_contain_no_secrets() -> None:
    """Диагностика конфигурации не раскрывает секреты (``CLAUDE.md`` §49)."""
    document = base_document()
    document["notifications"] = {
        "enabled": True,
        "telegram": {
            "enabled": True,
            "bot_token": {"env": "MONIK_TELEGRAM_BOT_TOKEN"},
            "chat_id": {"env": "MONIK_TELEGRAM_CHAT_ID"},
        },
    }
    loaded = parse_configuration(document, environ=dict(ENV))

    diagnostics = json.dumps(configuration_diagnostics(loaded), ensure_ascii=False)
    dumped = json.dumps(loaded.config.model_dump(mode="json"), ensure_ascii=False)

    for secret in SECRETS:
        assert secret not in diagnostics
        assert secret not in dumped
