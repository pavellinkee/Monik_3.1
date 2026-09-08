"""Architecture tests: Scheduler не содержит бизнес-логики.

``14_SCHEDULER.md`` §3: Scheduler координирует **когда** выполнять задачу.
Само действие принадлежит соответствующей подсистеме.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
SCHEDULER_ROOT = PACKAGE_ROOT / "services" / "scheduler"

#: Подсистемы, которые Scheduler не должен вызывать напрямую.
FORBIDDEN_MODULES = (
    "httpx",
    "requests",
    "aiohttp",
    "sqlite3",
    "aiosqlite",
    "monik.infrastructure.http",
    "monik.infrastructure.providers",
    "monik.infrastructure.telegram",
    "monik.services.level1",
    "monik.services.level2",
    "monik.services.calculator",
    "monik.services.notifications",
    "monik.services.fees",
    "monik.services.commands",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


SCHEDULER_FILES = _python_files(SCHEDULER_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_scheduler_exists() -> None:
    assert SCHEDULER_FILES


@pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
def test_scheduler_has_no_business_logic(path: pathlib.Path) -> None:
    """Планировщик не вызывает подсистемы напрямую (§3)."""
    for module in _imports(path):
        for forbidden in FORBIDDEN_MODULES:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports {module}: the scheduler must only trigger handlers"
            )


@pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
def test_scheduler_has_no_own_infinite_timer(path: pathlib.Path) -> None:
    """Собственный бесконечный цикл запрещён: тик задаёт приложение."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            assert not (isinstance(node.test, ast.Constant) and node.test.value is True), (
                f"{path.name} contains an infinite loop"
            )


@pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
def test_scheduler_uses_injected_clock(path: pathlib.Path) -> None:
    """Время берётся из инъектируемого Clock, а не из системных часов."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"utcnow", "today"}
    ]
    assert not offending, f"{path.name} reads the system clock at lines {offending}"


@pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
def test_scheduler_never_assumes_utc_for_daily_tasks(path: pathlib.Path) -> None:
    """Timezone задаётся явно (§9): фиксированный offset не используется."""
    source = path.read_text(encoding="utf-8")
    assert "timedelta(hours=1)  # DST" not in source
    if "at_time" in source and "ZoneInfo" not in source and "timezone_name" not in source:
        pytest.fail(f"{path.name} handles daily time without an explicit timezone")
