"""Security regression: SSRF, SQL, изоляция БД и отсутствие секретов в репозитории.

``22_SECURITY.md`` / ``32_SECURITY.md``: внешние запросы ограничены
allowlist'ом, SQL параметризован, тестовая БД не совпадает с production,
а секреты в репозиторий не попадают.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess

import pytest

import monik
from monik.domain.errors import DomainValidationError
from monik.infrastructure.http import UrlPolicy

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
PROJECT_ROOT = PACKAGE_ROOT.parent

#: Разрешённые хосты тестовой политики.
ALLOWED = ("api.1inch.dev", "api.0x.org")


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


SOURCE_FILES = _python_files(PACKAGE_ROOT)


# --- SSRF -----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://api.1inch.dev/quote",  # не https
        "https://127.0.0.1/quote",  # loopback
        "https://localhost/quote",  # loopback по имени
        "https://10.0.0.5/quote",  # приватная сеть
        "https://192.168.1.10/quote",  # приватная сеть
        "https://169.254.169.254/latest/meta",  # link-local metadata
        "https://[::1]/quote",  # loopback IPv6
        "https://user:pass@api.1inch.dev/q",  # credentials в URL
        "https://evil.example.com/quote",  # хост вне allowlist
    ],
)
def test_ssrf_candidates_are_rejected(url: str) -> None:
    """Опасные URL отклоняются до отправки запроса."""
    policy = UrlPolicy(ALLOWED)

    with pytest.raises(DomainValidationError):
        policy.validate(url)


def test_allowed_host_passes() -> None:
    policy = UrlPolicy(ALLOWED)
    assert policy.validate("https://api.1inch.dev/swap/v6.1/137/quote") == "api.1inch.dev"


def test_empty_allowlist_blocks_everything() -> None:
    """Пустой allowlist не означает «разрешено всё»."""
    policy = UrlPolicy(())
    assert policy.is_allowed("https://api.1inch.dev/quote") is False


# --- SQL ------------------------------------------------------------------


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_sql_is_parameterised(path: pathlib.Path) -> None:
    """SQL не собирается из пользовательских значений."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        literal = "".join(
            part.value for part in node.values if isinstance(part, ast.Constant)
        ).upper()
        if not any(
            keyword in literal for keyword in ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM")
        ):
            continue
        # Допустимы только подстановки списков колонок и placeholder'ов.
        for part in node.values:
            if isinstance(part, ast.Constant):
                continue
            name = getattr(part.value, "id", getattr(part.value, "attr", ""))
            if not name.startswith("_") and name not in {"placeholders", "table"}:
                offending.append((node.lineno, name))
    assert not offending, f"{path.name} builds SQL from a dynamic value: {offending}"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_string_concatenated_sql(path: pathlib.Path) -> None:
    """SQL не склеивается оператором ``+`` из переменных."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
            continue
        for side in (node.left, node.right):
            if isinstance(side, ast.Constant) and isinstance(side.value, str):
                upper = side.value.upper()
                assert not any(
                    keyword in upper
                    for keyword in ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM")
                ), f"{path.name}:{node.lineno} concatenates SQL"


# --- изоляция и файлы -----------------------------------------------------


def test_repository_contains_no_secret_values() -> None:
    """В репозитории нет реальных секретов (``CLAUDE.md`` §49)."""
    patterns = (
        re.compile(r"(?<![\w:])\d{9,10}:[A-Za-z0-9_-]{35}"),  # telegram bot token
        re.compile(r"0x[a-fA-F0-9]{64}"),  # приватный ключ
    )
    tracked = subprocess.run(  # noqa: S603
        ["git", "ls-files"],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    offenders: list[str] = []
    for name in tracked:
        candidate = PROJECT_ROOT / name
        if candidate.suffix not in {".py", ".yaml", ".yml", ".md", ".toml", ".env", ""}:
            continue
        if not candidate.is_file():
            continue
        content = candidate.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern.search(content):
                offenders.append(name)
    assert not offenders, f"possible secret material committed in: {sorted(set(offenders))}"


def test_example_env_has_no_values() -> None:
    """``.env.example`` содержит только имена переменных."""
    content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, _, value = stripped.partition("=")
        assert value == "", f"{name} in .env.example must not carry a value"


def test_example_config_uses_secret_references_only() -> None:
    """Пример конфигурации ссылается на окружение, а не на значения."""
    content = (PROJECT_ROOT / "config" / "config.example.yaml").read_text(encoding="utf-8")
    for line in content.splitlines():
        if "api_key" in line or "bot_token" in line or "chat_id" in line:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "env:" in stripped, f"secret must be a reference: {stripped}"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_path_traversal_literals(path: pathlib.Path) -> None:
    """Относительные переходы вверх не используются в путях.

    Проверяются только строковые литералы кода: docstrings исключены,
    поскольку они не участвуют в построении путей. Одиночный ``".."``
    допустим — он используется в проверке, запрещающей traversal.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    offending = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node not in docstrings
        and "../" in node.value
    ]
    assert not offending, f"{path.name} builds a traversal path at lines {offending}"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_tls_verification_is_never_disabled(path: pathlib.Path) -> None:
    """Проверка TLS не отключается (``06`` §79)."""
    source = path.read_text(encoding="utf-8")
    assert "verify=False" not in source
    assert "verify_tls=False" not in source
