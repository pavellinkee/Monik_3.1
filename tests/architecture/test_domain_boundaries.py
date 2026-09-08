"""Architecture tests: границы domain layer.

Domain не должен зависеть от HTTP, SQLite, Telegram, provider SDK и
environment variables (``25_PROJECT_STRUCTURE.md`` §8, §101,
``36_DATA_MODELS.md`` §3).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
DOMAIN_ROOT = PACKAGE_ROOT / "domain"

FORBIDDEN_IN_DOMAIN = {
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "sqlite3",
    "aiosqlite",
    "telegram",
    "yaml",
}

FORBIDDEN_PACKAGE_PREFIXES = (
    "monik.infrastructure",
    "monik.repositories",
    "monik.services",
    "monik.app",
    "monik.config",
)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


DOMAIN_FILES = _python_files(DOMAIN_ROOT)


def test_domain_has_modules() -> None:
    assert DOMAIN_FILES, "domain layer must contain modules"


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=lambda p: p.name)
def test_domain_does_not_import_infrastructure(path: pathlib.Path) -> None:
    for module in _imported_modules(path):
        root = module.split(".")[0]
        assert root not in FORBIDDEN_IN_DOMAIN, f"{path.name} imports forbidden module {module}"


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=lambda p: p.name)
def test_domain_does_not_import_upper_layers(path: pathlib.Path) -> None:
    for module in _imported_modules(path):
        for prefix in FORBIDDEN_PACKAGE_PREFIXES:
            assert not module.startswith(prefix), (
                f"{path.name} imports {module}; domain must not depend on upper layers"
            )


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=lambda p: p.name)
def test_domain_does_not_read_environment(path: pathlib.Path) -> None:
    """Business logic не читает environment напрямую (25 §64)."""
    source = path.read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source


@pytest.mark.parametrize("path", DOMAIN_FILES, ids=lambda p: p.name)
def test_domain_does_not_use_float_type(path: pathlib.Path) -> None:
    """float запрещён для финансовых значений (CLAUDE.md §11).

    В domain layer он допускается только в проверках, которые его отклоняют,
    поэтому такие места помечаются явным исключением.
    """
    allowed = {"numeric.py", "fingerprints.py"}
    if path.name in allowed:
        return
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float":
            pytest.fail(f"{path.name} references float")
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            pytest.fail(f"{path.name} contains a float literal")


def test_domain_models_are_frozen() -> None:
    """Доменные модели immutable (36 §74, 35 §4)."""
    from monik.domain import models

    for name in models.__all__:
        attribute = getattr(models, name)
        if isinstance(attribute, type) and issubclass(attribute, models.DomainModel):
            assert attribute.model_config.get("frozen") is True, f"{name} must be frozen"


def test_domain_models_forbid_unknown_fields() -> None:
    """Provider-specific поля не протекают в domain (36 §99.12)."""
    from monik.domain import models

    for name in models.__all__:
        attribute = getattr(models, name)
        if isinstance(attribute, type) and issubclass(attribute, models.DomainModel):
            assert attribute.model_config.get("extra") == "forbid", f"{name} must forbid extras"
