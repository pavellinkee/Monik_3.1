"""Smoke-тесты фундамента проекта (этап S0)."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import monik

EXPECTED_PACKAGES = [
    "monik.app",
    "monik.config",
    "monik.domain",
    "monik.domain.models",
    "monik.domain.enums",
    "monik.domain.value_objects",
    "monik.domain.errors",
    "monik.services",
    "monik.services.level1",
    "monik.services.level2",
    "monik.services.opportunity",
    "monik.services.calculator",
    "monik.services.fees",
    "monik.services.gas",
    "monik.services.prices",
    "monik.services.resources",
    "monik.services.scheduler",
    "monik.services.notifications",
    "monik.services.registries",
    "monik.services.health",
    "monik.services.observability",
    "monik.repositories",
    "monik.repositories.interfaces",
    "monik.repositories.sqlite",
    "monik.infrastructure",
    "monik.infrastructure.http",
    "monik.infrastructure.db",
    "monik.infrastructure.telegram",
    "monik.infrastructure.providers",
    "monik.infrastructure.providers.oneinch",
    "monik.infrastructure.providers.zero_x",
    "monik.infrastructure.providers.velora",
    "monik.infrastructure.providers.uniswap",
]


def test_version_is_exposed() -> None:
    assert monik.__version__ == "0.1.0"


@pytest.mark.parametrize("module_name", EXPECTED_PACKAGES)
def test_architecture_package_exists(module_name: str) -> None:
    """Каждый архитектурный слой представлен импортируемым пакетом."""
    module = importlib.import_module(module_name)
    assert module.__doc__, f"{module_name} должен иметь docstring с описанием ответственности"


def test_every_package_is_importable() -> None:
    """Ни один модуль пакета не должен падать при импорте."""
    failures: list[str] = []
    for module_info in pkgutil.walk_packages(monik.__path__, prefix="monik."):
        try:
            importlib.import_module(module_info.name)
        except Exception as exc:  # noqa: BLE001 - собираем все ошибки разом
            failures.append(f"{module_info.name}: {exc!r}")
    assert not failures, failures


def test_package_is_typed() -> None:
    """Пакет помечен как типизированный (py.typed)."""
    marker = next(iter(monik.__path__)) + "/py.typed"
    with open(marker):
        pass
