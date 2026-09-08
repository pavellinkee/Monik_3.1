"""Architecture tests: направление зависимостей и запрещённые импорты.

``25_PROJECT_STRUCTURE.md`` §8, §101: ``app → services → domain``.
Infrastructure подключается через интерфейсы, а provider-specific логика
остаётся внутри соответствующего адаптера (``CLAUDE.md`` §7).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))

#: Слои и то, что им запрещено импортировать.
FORBIDDEN_BY_LAYER: dict[str, tuple[str, ...]] = {
    "domain": (
        "monik.app",
        "monik.services",
        "monik.config",
        "monik.infrastructure",
        "monik.repositories",
    ),
    # Observability (Clock, редакция секретов) — cross-cutting утилита:
    # конфигурация регистрирует в ней секреты, но бизнес-подсистемы не знает.
    "config": (
        "monik.app",
        "monik.repositories",
        "monik.services.level1",
        "monik.services.level2",
        "monik.services.calculator",
        "monik.services.notifications",
        "monik.services.commands",
        "monik.services.scheduler",
        "monik.services.registries",
    ),
    "repositories": ("monik.app", "monik.services"),
}

#: Модули, которым разрешено читать переменные окружения
#: (``17_CONFIGURATION.md``: единственное место разрешения секретов).
ENVIRON_OWNERS = (
    PACKAGE_ROOT / "config" / "secrets.py",
    # Loader читает окружение для overrides ``MONIK__SECTION__FIELD``.
    PACKAGE_ROOT / "config" / "loader.py",
)

#: HTTP-библиотеки допустимы только в HTTP-инфраструктуре.
HTTP_OWNERS = (PACKAGE_ROOT / "infrastructure" / "http",)

#: Драйвер SQLite допустим только в db-слое и репозиториях.
SQLITE_OWNERS = (
    PACKAGE_ROOT / "infrastructure" / "db",
    PACKAGE_ROOT / "repositories",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


SOURCE_FILES = _python_files(PACKAGE_ROOT)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _owned_by(path: pathlib.Path, owners: tuple[pathlib.Path, ...]) -> bool:
    return any(path == owner or owner in path.parents for owner in owners)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_layer_dependencies_point_inwards(path: pathlib.Path) -> None:
    """Зависимости направлены внутрь: app → services → domain."""
    relative = path.relative_to(PACKAGE_ROOT)
    layer = relative.parts[0] if relative.parts else ""
    forbidden = FORBIDDEN_BY_LAYER.get(layer)
    if not forbidden:
        return
    for module in _imports(path):
        for item in forbidden:
            assert module != item and not module.startswith(f"{item}."), (
                f"{relative} imports {module}: it breaks the layering direction"
            )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_environment_is_read_in_one_place(path: pathlib.Path) -> None:
    """Переменные окружения читает только Secret Resolver."""
    if _owned_by(path, ENVIRON_OWNERS):
        return
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            offending.append(node.lineno)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"getenv", "environ"}
        ):
            offending.append(node.lineno)
    assert not offending, (
        f"{path.name} reads the environment directly at lines {offending}; "
        "secrets are resolved only by the configuration subsystem"
    )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_http_library_is_isolated(path: pathlib.Path) -> None:
    """``httpx`` используется только внутри HTTP-инфраструктуры."""
    if _owned_by(path, HTTP_OWNERS):
        return
    for module in _imports(path):
        assert module.split(".")[0] not in {"httpx", "requests", "aiohttp"}, (
            f"{path.name} imports an HTTP library outside the HTTP infrastructure"
        )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_sqlite_driver_is_isolated(path: pathlib.Path) -> None:
    """Драйвер SQLite используется только в db-слое и репозиториях."""
    if _owned_by(path, SQLITE_OWNERS):
        return
    for module in _imports(path):
        assert module.split(".")[0] not in {"sqlite3", "aiosqlite"}, (
            f"{path.name} imports a SQLite driver outside the persistence layer"
        )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_core_has_no_aggregator_branches(path: pathlib.Path) -> None:
    """В core нет ветвлений по идентификатору агрегатора (``CLAUDE.md`` §7).

    Provider-specific поведение принадлежит адаптеру; сравнение
    идентификатора провайдера в core означало бы обратное.
    """
    if _owned_by(path, (PACKAGE_ROOT / "infrastructure" / "providers",)):
        return
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for compare in ast.walk(node.test):
            if not isinstance(compare, ast.Compare):
                continue
            names = {
                child.attr for child in ast.walk(compare) if isinstance(child, ast.Attribute)
            } | {child.id for child in ast.walk(compare) if isinstance(child, ast.Name)}
            if "ProviderId" in names and any(isinstance(op, ast.Eq | ast.Is) for op in compare.ops):
                offending.append(node.lineno)
    assert not offending, f"{path.name} branches on a specific aggregator at lines {offending}"


def test_no_circular_imports() -> None:
    """Пакет импортируется целиком без циклических зависимостей."""
    import importlib

    for path in SOURCE_FILES:
        relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
        parts = [part for part in relative.parts if part != "__init__"]
        module = ".".join(("monik", *parts))
        importlib.import_module(module)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_float_in_financial_paths(path: pathlib.Path) -> None:
    """Финансовые значения не строятся из binary float (``CLAUDE.md`` §11)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")
        if name != "Decimal":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, float):
                offending.append(node.lineno)
    assert not offending, f"{path.name} builds a Decimal from a float at lines {offending}"
