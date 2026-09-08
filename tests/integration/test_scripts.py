"""Операционные скрипты: инициализация, резервная копия и восстановление."""

from __future__ import annotations

import pathlib

import pytest
import yaml

from monik.config.sections.database import DatabaseConfig
from monik.infrastructure.db import Database, MigrationRunner
from scripts import backup_db, init_db, restore_db
from tests.unit.config.conftest import VALID_ENV, base_document


@pytest.fixture
def config_path(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Конфигурация с базой во временном каталоге."""
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    document = base_document()
    document["database"] = {"path": str(tmp_path / "monik.db")}
    document["gas"] = {"sources": ["static"], "static_wei_per_gas": {"polygon": 5_000_000_000}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_init_db_creates_schema(config_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Скрипт создаёт базу и применяет миграции."""
    assert init_db.main(["--config", str(config_path)]) == 0
    assert (tmp_path / "monik.db").is_file()


def test_init_db_is_idempotent(config_path: pathlib.Path) -> None:
    """Повторный запуск на актуальной базе ничего не ломает."""
    assert init_db.main(["--config", str(config_path)]) == 0
    assert init_db.main(["--config", str(config_path)]) == 0


def test_backup_and_restore_round_trip(config_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Резервная копия проверяется и восстанавливается."""
    assert init_db.main(["--config", str(config_path)]) == 0
    backups = tmp_path / "backups"

    assert backup_db.main(["--config", str(config_path), "--output", str(backups)]) == 0
    created = sorted(backups.glob("monik-*.db"))
    assert len(created) == 1

    database_path = tmp_path / "monik.db"
    database_path.unlink()
    assert restore_db.main(["--config", str(config_path), "--backup", str(created[0])]) == 0
    assert database_path.is_file()


def test_restore_refuses_to_overwrite_silently(
    config_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Существующая база не перезаписывается без явного согласия."""
    assert init_db.main(["--config", str(config_path)]) == 0
    backups = tmp_path / "backups"
    assert backup_db.main(["--config", str(config_path), "--output", str(backups)]) == 0
    created = sorted(backups.glob("monik-*.db"))

    assert restore_db.main(["--config", str(config_path), "--backup", str(created[0])]) == 1
    assert (
        restore_db.main(["--config", str(config_path), "--backup", str(created[0]), "--force"]) == 0
    )


def test_backup_reports_missing_database(config_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Отсутствующая база — явная ошибка, а не пустая копия."""
    assert backup_db.main(["--config", str(config_path), "--output", str(tmp_path)]) == 1


def test_restore_reports_missing_backup(config_path: pathlib.Path) -> None:
    assert restore_db.main(["--config", str(config_path), "--backup", "missing.db"]) == 1


async def test_restored_database_passes_integrity_check(
    config_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Восстановленная база пригодна для запуска приложения."""
    backups = tmp_path / "backups"
    # В асинхронном тесте вызываются корутины скриптов напрямую: их
    # синхронные обёртки открывают собственный event loop.
    assert await init_db.initialise(str(config_path)) == 0
    assert await backup_db.run(str(config_path), str(backups)) == 0
    created = sorted(backups.glob("monik-*.db"))[0]

    database = Database(DatabaseConfig(path=str(created)))
    await database.connect()
    try:
        await database.check_integrity()
        versions = await MigrationRunner(database).applied_versions()
    finally:
        await database.close()

    assert versions
