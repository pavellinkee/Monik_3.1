"""Architecture tests: границы Notification System.

Критические инварианты ``15_NOTIFICATION_SYSTEM.md`` §80: подсистема не
содержит бизнес-логики сканера, ничего не пересчитывает, не обращается к
провайдерам котировок и не выполняет собственных HTTP-запросов в обход
адаптера.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
NOTIFICATIONS_ROOT = PACKAGE_ROOT / "services" / "notifications"
COMMANDS_ROOT = PACKAGE_ROOT / "services" / "commands"
TELEGRAM_ROOT = PACKAGE_ROOT / "infrastructure" / "telegram"

#: Notification System не должна знать сканер, адаптеры котировок и БД.
FORBIDDEN_IN_SERVICE = (
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "sqlite3",
    "aiosqlite",
    "monik.infrastructure.http",
    "monik.infrastructure.providers",
    "monik.services.level1",
    "monik.services.level2.scanner",
    "monik.services.calculator",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


NOTIFICATION_FILES = _python_files(NOTIFICATIONS_ROOT)
COMMAND_FILES = _python_files(COMMANDS_ROOT)
TELEGRAM_FILES = _python_files(TELEGRAM_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_notification_subsystem_exists() -> None:
    assert NOTIFICATION_FILES and TELEGRAM_FILES


@pytest.mark.parametrize("path", NOTIFICATION_FILES, ids=lambda p: p.name)
def test_notification_service_has_no_scanner_or_transport_details(
    path: pathlib.Path,
) -> None:
    """Подсистема работает с портами, а не с HTTP и сканером (§5-6, §10)."""
    for module in _imports(path):
        for forbidden in FORBIDDEN_IN_SERVICE:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports {module}: notification system must stay behind ports"
            )


@pytest.mark.parametrize("path", NOTIFICATION_FILES + TELEGRAM_FILES, ids=lambda p: p.name)
def test_notification_never_recalculates_financials(path: pathlib.Path) -> None:
    """Уведомление не пересчитывает прибыль (§14, §79, ``03`` §82).

    Финансовые значения только читаются из снимка: арифметика над ними
    означала бы второй источник истины.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    financial = {
        "net_profit",
        "gross_profit",
        "net_roi",
        "gross_roi",
        "total_fees",
        "gas_cost",
        "rebates",
        "other_costs",
        "total_costs",
    }
    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        names = {child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)} | {
            child.id for child in ast.walk(node) if isinstance(child, ast.Name)
        }
        hits = sorted(names & financial)
        if hits:
            offending.append((node.lineno, hits))
    assert not offending, f"{path.name} performs financial arithmetic: {offending}"


@pytest.mark.parametrize("path", TELEGRAM_FILES, ids=lambda p: p.name)
def test_telegram_adapter_goes_through_resource_manager(path: pathlib.Path) -> None:
    """Telegram-запросы проходят через Resource Manager (§29).

    Адаптер не создаёт собственных повторов и очередей.
    """
    source = path.read_text(encoding="utf-8")
    if "HttpRequest(" not in source:
        return
    assert "ResourceRequest(" in source, (
        f"{path.name} sends an HTTP request without a Resource Manager request"
    )
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True), (
                f"{path.name} implements its own retry loop"
            )


@pytest.mark.parametrize("path", NOTIFICATION_FILES + TELEGRAM_FILES, ids=lambda p: p.name)
def test_no_hardcoded_destination(path: pathlib.Path) -> None:
    """Chat ID и язык не зашиты в код (§51-53)."""
    source = path.read_text(encoding="utf-8")
    assert "-100" not in source, f"{path.name} looks like it hard-codes a chat id"


@pytest.mark.parametrize("path", COMMAND_FILES, ids=lambda p: p.name)
def test_command_handlers_never_reach_providers(path: pathlib.Path) -> None:
    """Обработчик команды не инициирует provider-запрос (``CLAUDE.md`` §35).

    Данные читаются только из репозиториев и уже собранных снимков, поэтому
    подсистема команд не знает ни адаптеров котировок, ни сканеров.
    """
    forbidden = (
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "monik.infrastructure.http",
        "monik.infrastructure.providers",
        "monik.services.level1",
        "monik.services.level2.scanner",
        "monik.services.level2.routes",
        "monik.services.calculator",
        "monik.services.resources",
    )
    for module in _imports(path):
        for item in forbidden:
            assert module != item and not module.startswith(f"{item}."), (
                f"{path.name} imports {module}: commands must read stored data only"
            )


def test_command_files_exist() -> None:
    assert COMMAND_FILES, "telegram command handling must be implemented"
