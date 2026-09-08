"""Architecture tests: финансовые формулы принадлежат Profit Calculator.

Level 1, Level 2, Telegram и история не должны реализовывать собственные
финансовые формулы (``09_PROFIT_CALCULATOR.md`` §2, §30, ``CLAUDE.md`` §25):
все они передают нормализованные данные единому Calculator.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import monik

PACKAGE_ROOT = pathlib.Path(next(iter(monik.__path__)))
CALCULATOR_ROOT = PACKAGE_ROOT / "services" / "calculator"

#: Модули, которым разрешено содержать финансовые формулы: сам Calculator
#: и его же контракт данных (``CostBreakdown.total_costs`` — часть формулы
#: §14 и хранится рядом с моделью результата).
FORMULA_OWNERS = (
    CALCULATOR_ROOT,
    PACKAGE_ROOT / "domain" / "models" / "profit.py",
)

#: Идентификаторы, арифметика над которыми и есть финансовая формула.
FINANCIAL_NAMES = (
    "gross_profit",
    "net_profit",
    "gross_roi",
    "net_roi",
    "total_costs",
    "total_fees",
    "other_costs",
    "gas_cost",
    "rebates",
)

#: Модули, которым разрешено сравнивать пороги: Calculator применяет порог,
#: конфигурация проверяет согласованность двух настроенных значений.
THRESHOLD_OWNERS = (
    CALCULATOR_ROOT,
    PACKAGE_ROOT / "config" / "sections" / "profitability.py",
)


#: Операторы, образующие проверку порога. ``is None`` проверкой порога
#: не является и не должен считаться нарушением.
THRESHOLD_OPERATORS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _is_owned_by(path: pathlib.Path, owners: tuple[pathlib.Path, ...]) -> bool:
    return any(path == owner or owner in path.parents for owner in owners)


SOURCE_FILES = _python_files(PACKAGE_ROOT)


def _identifiers(node: ast.AST) -> set[str]:
    """Имена и атрибуты, участвующие в выражении."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _financial_arithmetic(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        used = _identifiers(node)
        hits = sorted(name for name in used if name in FINANCIAL_NAMES)
        if hits:
            findings.append((node.lineno, ", ".join(hits)))
    return findings


def test_source_files_are_discovered() -> None:
    assert SOURCE_FILES, "package must contain modules"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_financial_formulas_live_only_in_calculator(path: pathlib.Path) -> None:
    """Арифметика над profit/ROI/costs допустима только в Calculator."""
    if _is_owned_by(path, FORMULA_OWNERS):
        return
    findings = _financial_arithmetic(path)
    assert not findings, (
        f"{path.relative_to(PACKAGE_ROOT)} computes financial values outside "
        f"Profit Calculator: {findings}"
    )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_threshold_comparison_lives_only_in_calculator(path: pathlib.Path) -> None:
    """Сравнение с порогом прибыльности выполняет только Calculator (§26)."""
    if _is_owned_by(path, THRESHOLD_OWNERS):
        return
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and "threshold" in _identifiers(node)
        and any(isinstance(op, THRESHOLD_OPERATORS) for op in node.ops)
    ]
    assert not offending, (
        f"{path.relative_to(PACKAGE_ROOT)} compares a profitability threshold "
        f"outside Profit Calculator at lines {offending}"
    )


def test_calculator_actually_owns_the_formulas() -> None:
    """Тест выше бессмыслен, если в Calculator формул нет."""
    findings = [
        finding
        for path in _python_files(CALCULATOR_ROOT)
        for finding in _financial_arithmetic(path)
    ]
    assert findings, "Profit Calculator must contain the financial formulas"


def test_calculator_performs_no_io() -> None:
    """Calculator не обращается к внешним API, БД и Scheduler (§74-76)."""
    forbidden = {
        "httpx",
        "aiosqlite",
        "sqlite3",
        "asyncio",
        "monik.infrastructure",
        "monik.repositories",
        "monik.app",
    }
    for path in _python_files(CALCULATOR_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                root = module.split(".")[0]
                assert root not in forbidden, f"{path.name} imports {module}"
                assert not any(
                    module.startswith(prefix) for prefix in forbidden if "." in prefix
                ), f"{path.name} imports {module}"
