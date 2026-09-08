"""Architecture tests: границы работы с базой данных.

Business logic не выполняет raw SQL и не импортирует драйвер SQLite
(``25_PROJECT_STRUCTURE.md`` §63, ``16_DATABASE.md`` §12-13).
Транзакция не удерживается во время внешнего запроса
(``30_DATABASE_SCHEMA.md`` §76-77).
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))

#: Слои, которым разрешено работать с драйвером SQLite напрямую.
DB_ALLOWED_PREFIXES = ("infrastructure/db", "repositories/sqlite")

SQL_STATEMENT = re.compile(
    r"\b(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+TABLE)\b",
    re.IGNORECASE,
)

#: Признаки внешнего вызова, который нельзя делать внутри транзакции.
EXTERNAL_CALL_MARKERS = (
    "http",
    "request",
    "telegram",
    "send_message",
    "get_quote",
    "fetch_url",
    "adapter",
)


def _python_files() -> list[pathlib.Path]:
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _relative(path: pathlib.Path) -> str:
    return path.relative_to(PACKAGE_ROOT).as_posix()


def _is_db_layer(path: pathlib.Path) -> bool:
    relative = _relative(path)
    return any(relative.startswith(prefix) for prefix in DB_ALLOWED_PREFIXES)


ALL_FILES = _python_files()
NON_DB_FILES = [path for path in ALL_FILES if not _is_db_layer(path)]


@pytest.mark.parametrize("path", NON_DB_FILES, ids=_relative)
def test_sqlite_driver_is_not_imported_outside_db_layer(path: pathlib.Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            root = module.split(".")[0]
            assert root not in {"sqlite3", "aiosqlite"}, (
                f"{_relative(path)} imports {module}; database access must go through "
                "the repository boundary"
            )


@pytest.mark.parametrize("path", NON_DB_FILES, ids=_relative)
def test_raw_sql_is_not_written_outside_db_layer(path: pathlib.Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_STATEMENT.search(node.value), (
                f"{_relative(path)} contains a raw SQL statement; SQL belongs to "
                "repositories/sqlite or infrastructure/db"
            )


def _transaction_blocks(tree: ast.AST) -> list[ast.AsyncWith]:
    blocks: list[ast.AsyncWith] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncWith):
            continue
        for item in node.items:
            expression = item.context_expr
            if isinstance(expression, ast.Call):
                function = expression.func
                name = function.attr if isinstance(function, ast.Attribute) else ""
                if name in {"transaction", "begin"}:
                    blocks.append(node)
                    break
    return blocks


@pytest.mark.parametrize("path", ALL_FILES, ids=_relative)
def test_transaction_never_wraps_external_call(path: pathlib.Path) -> None:
    """Транзакция не удерживается во время внешнего запроса (30 §77)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for block in _transaction_blocks(tree):
        for node in ast.walk(block):
            if not isinstance(node, ast.Await):
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            function = call.func
            name = function.attr if isinstance(function, ast.Attribute) else ""
            if isinstance(function, ast.Name):
                name = function.id
            lowered = name.lower()
            for marker in EXTERNAL_CALL_MARKERS:
                assert marker not in lowered, (
                    f"{_relative(path)}:{node.lineno} awaits {name!r} inside a database "
                    "transaction; external requests must happen outside transactions"
                )


HTTP_ALLOWED_PREFIXES = ("infrastructure/http",)

HTTP_LIBRARIES = frozenset({"httpx", "requests", "aiohttp", "urllib3"})


def _is_http_layer(path: pathlib.Path) -> bool:
    relative = _relative(path)
    return any(relative.startswith(prefix) for prefix in HTTP_ALLOWED_PREFIXES)


NON_HTTP_FILES = [path for path in ALL_FILES if not _is_http_layer(path)]


@pytest.mark.parametrize("path", NON_HTTP_FILES, ids=_relative)
def test_http_library_is_not_imported_outside_http_layer(path: pathlib.Path) -> None:
    """Business logic не импортирует HTTP-библиотеки (25 §62)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            root = module.split(".")[0]
            assert root not in HTTP_LIBRARIES, (
                f"{_relative(path)} imports {module}; external requests must go through "
                "the http infrastructure and the resource manager"
            )


def test_tls_verification_is_never_disabled() -> None:
    """Отключение проверки TLS запрещено (06 §79)."""
    for path in ALL_FILES:
        source = path.read_text(encoding="utf-8")
        assert "verify=False" not in source, f"{_relative(path)} disables TLS verification"


def test_database_layer_exists() -> None:
    assert (PACKAGE_ROOT / "infrastructure" / "db" / "connection.py").is_file()


def test_no_float_columns_in_schema() -> None:
    """Финансовые значения не хранятся как REAL (30 §56)."""
    migrations = (PACKAGE_ROOT / "infrastructure" / "db" / "migrations").rglob("*.py")
    for path in migrations:
        source = path.read_text(encoding="utf-8")
        assert " REAL" not in source.upper(), f"{path.name} declares a REAL column"


def test_schema_contains_no_secret_columns() -> None:
    """В схеме нет колонок для секретов (30 §58)."""
    path = PACKAGE_ROOT / "infrastructure" / "db" / "migrations" / "m0001_initial.py"
    source = path.read_text(encoding="utf-8").lower()
    for forbidden in ("api_key", "bot_token", "password", "private_key", "authorization"):
        assert forbidden not in source, f"schema declares a secret column: {forbidden}"
