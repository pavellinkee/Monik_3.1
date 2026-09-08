"""Резервное копирование базы Monik.

Используется online-backup SQLite: копия делается согласованной без
остановки приложения. Скрипт не читает бизнес-данные и не изменяет их.

Запуск::

    uv run python scripts/backup_db.py --config config/config.yaml --output backups/
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from monik.config import load_configuration
from monik.domain.errors import MonikError
from monik.infrastructure.db import Database


def build_parser() -> argparse.ArgumentParser:
    """Аргументы командной строки."""
    parser = argparse.ArgumentParser(prog="backup_db", description="back up the Monik database")
    parser.add_argument("--config", default="config/config.yaml", help="configuration file")
    parser.add_argument(
        "--output",
        default=None,
        help="backup directory (defaults to database.backup_directory)",
    )
    return parser


def backup_name(now: datetime) -> str:
    """Имя файла резервной копии."""
    return f"monik-{now.strftime('%Y%m%dT%H%M%SZ')}.db"


async def verify(path: pathlib.Path) -> None:
    """Проверить, что копия читается и цела."""
    from monik.config.sections.database import DatabaseConfig

    database = Database(DatabaseConfig(path=str(path), integrity_check_on_startup=False))
    await database.connect()
    try:
        await database.check_integrity()
    finally:
        await database.close()


async def run(config_path: str, output: str | None) -> int:
    """Создать резервную копию и проверить её."""
    loaded = load_configuration(config_path)
    source = pathlib.Path(loaded.config.database.path)
    if not source.is_file():
        sys.stderr.write(f"backup_db: database not found: {source}\n")
        return 1

    directory = pathlib.Path(output or loaded.config.database.backup_directory or "backups")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / backup_name(datetime.now(UTC))

    # Online backup: копия согласована даже при работающем приложении.
    with sqlite3.connect(source) as origin, sqlite3.connect(target) as copy:
        origin.backup(copy)

    await verify(target)
    sys.stdout.write(f"backup created: {target}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа скрипта."""
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(arguments.config, arguments.output))
    except MonikError as error:
        sys.stderr.write(f"backup_db: {error.info.code}: {error.info.message}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
