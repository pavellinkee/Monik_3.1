"""Восстановление базы Monik из резервной копии.

Восстановление выполняется только на остановленном приложении и никогда
не перезаписывает рабочую базу молча: существующий файл требуется
подтвердить флагом ``--force``.

Запуск::

    uv run python scripts/restore_db.py --config config/config.yaml --backup backups/monik.db
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import shutil
import sys
from collections.abc import Sequence

from monik.config import load_configuration
from monik.config.sections.database import DatabaseConfig
from monik.domain.errors import MonikError
from monik.infrastructure.db import Database, MigrationRunner


def build_parser() -> argparse.ArgumentParser:
    """Аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="restore_db", description="restore the Monik database from a backup"
    )
    parser.add_argument("--config", default="config/config.yaml", help="configuration file")
    parser.add_argument("--backup", required=True, help="backup file to restore")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the existing database file",
    )
    return parser


async def check_backup(path: pathlib.Path) -> tuple[int, ...]:
    """Проверить целостность копии и вернуть применённые версии схемы."""
    database = Database(DatabaseConfig(path=str(path), integrity_check_on_startup=False))
    await database.connect()
    try:
        await database.check_integrity()
        return await MigrationRunner(database).applied_versions()
    finally:
        await database.close()


async def run(config_path: str, backup: str, *, force: bool) -> int:
    """Восстановить базу из резервной копии."""
    loaded = load_configuration(config_path)
    source = pathlib.Path(backup)
    target = pathlib.Path(loaded.config.database.path)

    if not source.is_file():
        sys.stderr.write(f"restore_db: backup not found: {source}\n")
        return 1
    if target.exists() and not force:
        sys.stderr.write(f"restore_db: {target} already exists; pass --force to overwrite it\n")
        return 1

    versions = await check_backup(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    sys.stdout.write(
        f"restored: {target}\nschema versions: {', '.join(str(item) for item in versions)}\n"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа скрипта."""
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(arguments.config, arguments.backup, force=arguments.force))
    except MonikError as error:
        sys.stderr.write(f"restore_db: {error.info.code}: {error.info.message}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
