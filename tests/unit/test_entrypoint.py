"""Entrypoint: проверка конфигурации и коды возврата."""

from __future__ import annotations

import pathlib

import yaml

from monik.app.main import build_parser, main
from tests.unit.config.conftest import VALID_ENV, base_document


def write_config(path: pathlib.Path) -> pathlib.Path:
    """Записать минимальную валидную конфигурацию."""
    document = base_document()
    document["gas"] = {"sources": ["static"], "static_wei_per_gas": {"polygon": 120_000_000_000}}
    config_path = path / "config.yaml"
    config_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return config_path


def test_parser_defaults() -> None:
    arguments = build_parser().parse_args([])
    assert arguments.config == "config/config.yaml"
    assert arguments.check_config is False


def test_check_config_succeeds(tmp_path: pathlib.Path, monkeypatch: object) -> None:
    """``--check-config`` валидирует конфигурацию и не запускает воркеры."""
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)  # type: ignore[attr-defined]
    config_path = write_config(tmp_path)

    assert main(["--config", str(config_path), "--check-config"]) == 0


def test_missing_configuration_is_reported(tmp_path: pathlib.Path) -> None:
    """Отсутствующая конфигурация — явная ошибка, а не тихий старт."""
    assert main(["--config", str(tmp_path / "missing.yaml"), "--check-config"]) == 1


def test_invalid_configuration_is_reported(tmp_path: pathlib.Path, monkeypatch: object) -> None:
    """Невалидная конфигурация не заменяется безопасными на вид значениями."""
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)  # type: ignore[attr-defined]
    config_path = tmp_path / "broken.yaml"
    config_path.write_text(yaml.safe_dump({"networks": []}), encoding="utf-8")

    assert main(["--config", str(config_path), "--check-config"]) == 1
