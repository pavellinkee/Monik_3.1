"""Architecture tests: Health Monitoring не изменяет бизнес-состояние.

``19_HEALTH_MONITORING.md`` §54-56: health ≠ profitability,
health ≠ capability. Circuit Breaker и health не изменяют Capability
Registry (``05_RESOURCE_MANAGER.md`` §11).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
HEALTH_ROOT = PACKAGE_ROOT / "services" / "health"
SUPERVISOR = PACKAGE_ROOT / "app" / "supervisor.py"

#: Health не должен знать бизнес-подсистемы и хранилище.
FORBIDDEN_IN_HEALTH = (
    "httpx",
    "requests",
    "aiosqlite",
    "sqlite3",
    "monik.infrastructure",
    "monik.repositories",
    "monik.services.level1",
    "monik.services.level2",
    "monik.services.calculator",
    "monik.services.registries",
    "monik.services.notifications",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


HEALTH_FILES = _python_files(HEALTH_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_health_subsystem_exists() -> None:
    assert HEALTH_FILES and SUPERVISOR.exists()


@pytest.mark.parametrize("path", HEALTH_FILES, ids=lambda p: p.name)
def test_health_does_not_touch_business_subsystems(path: pathlib.Path) -> None:
    """Health только описывает состояние (``19`` §54-56)."""
    for module in _imports(path):
        for forbidden in FORBIDDEN_IN_HEALTH:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports {module}: health must not change business state"
            )


@pytest.mark.parametrize("path", HEALTH_FILES, ids=lambda p: p.name)
def test_health_never_writes_capabilities(path: pathlib.Path) -> None:
    """Health не изменяет Capability Registry (``05_RESOURCE_MANAGER.md`` §11)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"record_discovery", "record_failure", "record_success"}
        and isinstance(node.func.value, ast.Attribute | ast.Name)
        and getattr(node.func.value, "attr", getattr(node.func.value, "id", ""))
        in {"capabilities", "registry"}
    ]
    assert not offending, f"{path.name} writes capability state at lines {offending}"


def test_supervisor_reaches_safe_stop_on_persistence_failure() -> None:
    """SAFE_STOP описан явно в коде Supervisor (``CLAUDE.md`` §34)."""
    source = SUPERVISOR.read_text(encoding="utf-8")
    assert "DatabaseError" in source
    assert "SAFE_STOP" in source


def test_supervisor_has_no_business_logic() -> None:
    """Supervisor запускает корутины, но не реализует подсистемы."""
    forbidden = (
        "monik.services.level1",
        "monik.services.level2",
        "monik.services.notifications",
        "monik.infrastructure.providers",
        "monik.infrastructure.telegram",
    )
    for module in _imports(SUPERVISOR):
        for item in forbidden:
            assert module != item and not module.startswith(f"{item}."), (
                f"supervisor imports {module}: it must only run supplied workers"
            )
