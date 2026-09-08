"""Architecture tests: границы Level 1 Scanner.

Критические инварианты ``02_LEVEL1_SCANNER.md`` §96 и
``10_LEVEL_1_SCANNER.md`` §94: Level 1 не отправляет уведомления, не
обходит Resource Manager, не выполняет provider-specific HTTP-логику, не
создаёт собственный бесконечный таймер и не реализует финансовые формулы.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
LEVEL1_ROOT = PACKAGE_ROOT / "services" / "level1"

#: Модули, обращение к которым означало бы обход Adapter/Resource Manager.
FORBIDDEN_MODULES = (
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "socket",
    "sqlite3",
    "aiosqlite",
    "telegram",
    "monik.infrastructure.http",
    "monik.services.notifications",
    "monik.repositories.sqlite.notifications",
)

#: Функции, создающие собственный бесконечный таймер.
FORBIDDEN_CALLS = ("sleep_forever",)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


LEVEL1_FILES = _python_files(LEVEL1_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_level1_package_exists() -> None:
    assert LEVEL1_FILES, "Level 1 must be implemented"


@pytest.mark.parametrize("path", LEVEL1_FILES, ids=lambda p: p.name)
def test_level1_does_not_bypass_adapters_or_resource_manager(path: pathlib.Path) -> None:
    """Внешние запросы идут только через Adapter (§11, §96.3-4)."""
    for module in _imports(path):
        for forbidden in FORBIDDEN_MODULES:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports {module}: Level 1 must go through the adapter "
                "and Resource Manager"
            )


@pytest.mark.parametrize("path", LEVEL1_FILES, ids=lambda p: p.name)
def test_level1_never_sends_notifications(path: pathlib.Path) -> None:
    """Level 1 не отправляет Telegram-уведомления (``02`` §83, ``10`` §62)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    offending = sorted(
        name for name in names if "telegram" in name.lower() or "notif" in name.lower()
    )
    assert not offending, f"{path.name} references notification API: {offending}"


@pytest.mark.parametrize("path", LEVEL1_FILES, ids=lambda p: p.name)
def test_level1_has_no_own_timer(path: pathlib.Path) -> None:
    """Собственный бесконечный таймер запрещён (``02`` §63, ``10`` §65)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True), (
                f"{path.name} contains an infinite loop; the Scheduler starts scans"
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in FORBIDDEN_CALLS, f"{path.name} calls {node.func.attr}"


@pytest.mark.parametrize("path", LEVEL1_FILES, ids=lambda p: p.name)
def test_level1_does_not_hardcode_scan_parameters(path: pathlib.Path) -> None:
    """Токены, суммы и пороги задаются конфигурацией (``02`` §5)."""
    source = path.read_text(encoding="utf-8").lower()
    for literal in ("usdt", "aave", "0x", "top_30"):
        assert literal not in source, f"{path.name} hard-codes scan parameter {literal!r}"
