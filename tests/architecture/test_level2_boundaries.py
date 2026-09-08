"""Architecture tests: границы Level 2 Scanner.

Критические инварианты ``11_LEVEL_2_SCANNER.md`` §76: Level 2 не выбирает
новый маршрут, не выполняет route optimization, не обходит Resource
Manager, не реализует собственную формулу прибыли и не отправляет
уведомления.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
LEVEL2_ROOT = PACKAGE_ROOT / "services" / "level2"

#: Обращение к ним означало бы обход Adapter/Resource Manager.
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
    # Level 2 не выполняет поиск маршрута и не запускает цикл Level 1.
    "monik.services.level1",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


LEVEL2_FILES = _python_files(LEVEL2_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_level2_package_exists() -> None:
    assert LEVEL2_FILES, "Level 2 must be implemented"


@pytest.mark.parametrize("path", LEVEL2_FILES, ids=lambda p: p.name)
def test_level2_does_not_bypass_adapters_or_resource_manager(path: pathlib.Path) -> None:
    """Внешние запросы идут только через Adapter (§29, §76.7)."""
    for module in _imports(path):
        for forbidden in FORBIDDEN_MODULES:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports {module}: Level 2 must go through the adapter "
                "and Resource Manager"
            )


@pytest.mark.parametrize("path", LEVEL2_FILES, ids=lambda p: p.name)
def test_level2_never_sends_notifications(path: pathlib.Path) -> None:
    """Уведомления отправляет Notification layer (``03`` §52-53)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    offending = sorted(name for name in names if "telegram" in name.lower())
    assert not offending, f"{path.name} references Telegram API: {offending}"


@pytest.mark.parametrize("path", LEVEL2_FILES, ids=lambda p: p.name)
def test_level2_only_requests_fixed_routes(path: pathlib.Path) -> None:
    """Свободный поиск маршрута запрещён (§5, §61, §76.13).

    Level 2 обязан строить запрос с ``fixed_route``: запрос котировки без
    зафиксированного маршрута означал бы подбор нового пути.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")
        if name != "QuoteRequest":
            continue
        keywords = {keyword.arg for keyword in node.keywords}
        assert "fixed_route" in keywords, (
            f"{path.name}:{node.lineno} builds a quote request without a fixed route"
        )


@pytest.mark.parametrize("path", LEVEL2_FILES, ids=lambda p: p.name)
def test_level2_does_not_call_plain_get_quote(path: pathlib.Path) -> None:
    """Проверка выполняется через ``validate_fixed_route`` (§19-21)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_quote"
    ]
    assert not offending, (
        f"{path.name} calls get_quote directly at lines {offending}; "
        "Level 2 must verify the fixed route"
    )
