"""Root pytest configuration.

Общие fixtures добавляются по мере реализации подсистем.
Тесты никогда не должны использовать production database или реальные credentials
(``23_TESTING.md`` §10, §15-16).
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """Абсолютный путь к корню репозитория."""
    return REPO_ROOT


@pytest.fixture
def tmp_data_dir(tmp_path: pathlib.Path) -> Iterator[pathlib.Path]:
    """Изолированный каталог для runtime-данных теста (БД, файлы состояния)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    yield data_dir
