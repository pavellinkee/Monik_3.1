"""Security-тесты: секреты не должны попадать в логи и диагностику.

Обязательное требование ``CLAUDE.md`` §48-49 и ``17_CONFIGURATION.md`` §48, §58:
секреты не логируются ни при каком уровне логирования.
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from monik.domain.errors import AuthenticationError, ProviderError
from monik.services.observability import (
    REDACTED,
    SecretRegistry,
    configure_logging,
    get_logger,
    log_context,
    log_fields,
    redact_mapping,
    redact_text,
)

BOT_TOKEN = "8123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
API_KEY = "sk-live-9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c"
PRIVATE_KEY = "0x" + "a1b2c3d4" * 8


@pytest.fixture
def registry() -> SecretRegistry:
    instance = SecretRegistry()
    instance.register(BOT_TOKEN)
    instance.register(API_KEY)
    instance.register(PRIVATE_KEY)
    return instance


class TestRedactText:
    def test_registered_secret_is_removed(self, registry: SecretRegistry) -> None:
        result = redact_text(f"calling telegram with {BOT_TOKEN}", registry=registry)
        assert BOT_TOKEN not in result
        assert REDACTED in result

    def test_bearer_token_is_removed_without_registration(self) -> None:
        result = redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_telegram_token_shape_is_removed_without_registration(self) -> None:
        result = redact_text(f"url https://api.telegram.org/bot{BOT_TOKEN}/sendMessage")
        assert BOT_TOKEN not in result

    def test_private_key_shape_is_removed(self) -> None:
        result = redact_text(f"key={PRIVATE_KEY}")
        assert PRIVATE_KEY not in result

    def test_key_value_pair_is_removed(self) -> None:
        result = redact_text("request failed: api_key=abcdef123456 network=polygon")
        assert "abcdef123456" not in result
        assert "polygon" in result

    def test_regular_text_is_preserved(self, registry: SecretRegistry) -> None:
        text = "scan complete: 12 quotes, 2 opportunities on polygon"
        assert redact_text(text, registry=registry) == text

    def test_short_values_are_not_registered(self) -> None:
        short = SecretRegistry()
        short.register("abc")
        assert len(short) == 0
        assert redact_text("abc value", registry=short) == "abc value"


class TestRedactMapping:
    def test_sensitive_keys_are_redacted(self) -> None:
        result = redact_mapping({"api_key": "x", "bot_token": "y", "password": "z"})
        assert set(result.values()) == {REDACTED}

    def test_business_token_fields_are_preserved(self) -> None:
        """Поля с токенами торговых пар секретами не являются."""
        data = {
            "input_token": "polygon:0xabc",
            "output_token": "polygon:0xdef",
            "native_token": "WMATIC",
        }
        assert redact_mapping(data) == data

    def test_nested_structures_are_redacted(self, registry: SecretRegistry) -> None:
        data = {
            "provider": {"name": "oneinch", "credentials": {"api_key": API_KEY}},
            "messages": [f"used {API_KEY}"],
        }
        result = redact_mapping(data, registry=registry)
        assert API_KEY not in json.dumps(result)

    def test_secret_in_unexpected_field_is_still_removed(self, registry: SecretRegistry) -> None:
        """Защита работает и по значению, а не только по имени поля."""
        result = redact_mapping({"message": f"token is {BOT_TOKEN}"}, registry=registry)
        assert BOT_TOKEN not in json.dumps(result)


class TestStructuredLoggerNeverLeaksSecrets:
    def _configure(self, registry: SecretRegistry, level: str = "DEBUG") -> io.StringIO:
        stream = io.StringIO()
        configure_logging(level=level, stream=stream, registry=registry)
        return stream

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_secret_never_appears_at_any_level(self, registry: SecretRegistry, level: str) -> None:
        stream = self._configure(registry, level="DEBUG")
        logger = get_logger("test.secrets")
        getattr(logger, level.lower())("sending with %s", BOT_TOKEN)
        output = stream.getvalue()
        assert output
        assert BOT_TOKEN not in output
        assert REDACTED in output

    def test_secret_in_structured_field_is_redacted(self, registry: SecretRegistry) -> None:
        stream = self._configure(registry)
        get_logger("test.fields").info("request", extra=log_fields(api_key=API_KEY))
        output = stream.getvalue()
        assert API_KEY not in output

    def test_secret_in_exception_message_is_redacted(self, registry: SecretRegistry) -> None:
        stream = self._configure(registry)
        logger = get_logger("test.exceptions")
        try:
            raise AuthenticationError(f"rejected key {API_KEY}")
        except AuthenticationError:
            logger.exception("provider auth failed")
        output = stream.getvalue()
        assert API_KEY not in output

    def test_secret_in_correlation_context_is_redacted(self, registry: SecretRegistry) -> None:
        stream = self._configure(registry)
        with log_context(provider=f"oneinch-{API_KEY}"):
            get_logger("test.context").info("scanning")
        assert API_KEY not in stream.getvalue()

    def test_traceback_is_not_emitted(self, registry: SecretRegistry) -> None:
        """Traceback может содержать значения переменных, включая секреты."""
        stream = self._configure(registry)
        logger = get_logger("test.traceback")
        try:
            raise ProviderError("upstream failure")
        except ProviderError:
            logger.exception("failed")
        output = stream.getvalue()
        assert "Traceback" not in output
        assert "test_secret_redaction.py" not in output


class TestStructuredLogFormat:
    def _record(self, stream: io.StringIO) -> dict[str, object]:
        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert isinstance(parsed, dict)
        return parsed

    def test_emits_single_json_line(self) -> None:
        stream = io.StringIO()
        configure_logging(level="INFO", stream=stream, registry=SecretRegistry())
        get_logger("test.format").info("scan started")
        record = self._record(stream)
        assert record["message"] == "scan started"
        assert record["level"] == "INFO"
        assert record["logger"] == "monik.test.format"
        assert record["timestamp"]

    def test_includes_correlation_fields(self) -> None:
        stream = io.StringIO()
        configure_logging(level="INFO", stream=stream, registry=SecretRegistry())
        with log_context(scan_id="scan-1", k_id="#K1234", provider="oneinch"):
            get_logger("test.format").info("verifying")
        record = self._record(stream)
        assert record["scan_id"] == "scan-1"
        assert record["k_id"] == "#K1234"
        assert record["provider"] == "oneinch"

    def test_includes_structured_fields(self) -> None:
        stream = io.StringIO()
        configure_logging(level="INFO", stream=stream, registry=SecretRegistry())
        get_logger("test.format").info(
            "quote received", extra=log_fields(duration_ms=42, network="polygon")
        )
        record = self._record(stream)
        assert record["duration_ms"] == 42
        assert record["network"] == "polygon"

    def test_includes_normalized_error_classification(self) -> None:
        stream = io.StringIO()
        configure_logging(level="INFO", stream=stream, registry=SecretRegistry())
        logger = get_logger("test.format")
        try:
            raise ProviderError("upstream failure", provider_code="E42")
        except ProviderError:
            logger.exception("request failed")
        record = self._record(stream)
        assert record["error_code"] == "provider_error"
        assert record["error_category"] == "provider"
        assert record["error_retryability"] == "conditional"


def teardown_module() -> None:
    """Вернуть логирование в исходное состояние после модуля."""
    logging.getLogger("monik").handlers.clear()


class TestHttpDoesNotLeakCredentials:
    """Заголовок авторизации не должен попадать в логи (06 §66)."""

    def test_authorization_header_is_redacted_in_logs(self, registry: SecretRegistry) -> None:
        from monik.infrastructure.http import HttpRequest
        from monik.services.observability import log_fields

        stream = io.StringIO()
        configure_logging(level="INFO", stream=stream, registry=registry)
        request = HttpRequest(
            method="GET",
            url="https://api.example.com/quote",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        get_logger("test.http").info(
            "sending request",
            extra=log_fields(url=request.url, headers=request.headers),
        )
        output = stream.getvalue()
        assert API_KEY not in output
        assert "api.example.com" in output

    def test_request_repr_is_not_logged_raw(self, registry: SecretRegistry) -> None:
        from monik.infrastructure.http import HttpRequest

        stream = io.StringIO()
        configure_logging(level="DEBUG", stream=stream, registry=registry)
        request = HttpRequest(
            method="GET",
            url="https://api.example.com/quote",
            headers={"x-api-key": API_KEY},
        )
        get_logger("test.http").debug("request %s", request)
        assert API_KEY not in stream.getvalue()
