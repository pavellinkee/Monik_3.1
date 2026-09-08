"""Тесты переопределения конфигурации через environment."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from monik.config import parse_configuration
from monik.config.sections import Environment
from monik.domain.errors import ConfigurationError


def _load(document: dict[str, Any], env: dict[str, str]) -> Any:
    return parse_configuration(document, environ=env).config


class TestEnvironmentOverrides:
    def test_overrides_nested_value(self, document: dict[str, Any], env: dict[str, str]) -> None:
        env["MONIK__SCANNER__LEVEL1__INTERVAL_SECONDS"] = "600"
        config = _load(document, env)
        assert config.scanner.level1.interval_seconds == 600

    def test_environment_wins_over_file(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        """Приоритет: env override > file > default (17 §59)."""
        document["application"]["environment"] = "development"
        env["MONIK__APPLICATION__ENVIRONMENT"] = "test"
        assert _load(document, env).application.environment is Environment.TEST

    def test_file_wins_over_default(self, document: dict[str, Any], env: dict[str, str]) -> None:
        document["scanner"]["level2"] = {"max_parallel": 5}
        assert _load(document, env).scanner.level2.max_parallel == 5

    def test_default_applies_when_absent(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        assert _load(document, env).scanner.level2.max_parallel == 20

    def test_boolean_coercion(self, document: dict[str, Any], env: dict[str, str]) -> None:
        env["MONIK__METRICS__ENABLED"] = "false"
        assert _load(document, env).metrics.enabled is False

    def test_list_coercion(self, document: dict[str, Any], env: dict[str, str]) -> None:
        env["MONIK__SCANNER__AMOUNTS"] = "100,250,500"
        config = _load(document, env)
        assert config.scanner.amounts == (Decimal("100"), Decimal("250"), Decimal("500"))

    def test_decimal_override_is_not_converted_to_float(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        """Финансовое значение из env остаётся точным (17 §20)."""
        env["MONIK__PROFITABILITY__FINAL_THRESHOLD_PERCENT"] = "1.25"
        threshold = _load(document, env).profitability.final_threshold_percent
        assert threshold == Decimal("1.25")
        assert isinstance(threshold, Decimal)

    def test_creates_missing_intermediate_sections(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        env["MONIK__DATABASE__PATH"] = "data/custom.db"
        assert _load(document, env).database.path == "data/custom.db"

    def test_unrelated_environment_variables_are_ignored(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        env["PATH"] = "/usr/bin"
        env["MONIK_ONEINCH_API_KEY"] = "oneinch-example-key-value"
        assert _load(document, env).scanner.level1.interval_seconds == 300

    def test_override_into_non_mapping_is_rejected(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        env["MONIK__SCANNER__BASE_NETWORK__NESTED"] = "x"
        with pytest.raises(ConfigurationError, match="non-mapping"):
            _load(document, env)

    def test_invalid_override_value_is_reported(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        env["MONIK__SCANNER__LEVEL2__MAX_PARALLEL"] = "not-a-number"
        with pytest.raises(ConfigurationError, match="max_parallel"):
            _load(document, env)

    def test_empty_path_override_is_reported(
        self, document: dict[str, Any], env: dict[str, str]
    ) -> None:
        env["MONIK__"] = "x"
        with pytest.raises(ConfigurationError, match="configuration path"):
            _load(document, env)
