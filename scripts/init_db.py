"""Инициализация базы данных Monik.

Скрипт не дублирует business logic (``25_PROJECT_STRUCTURE.md`` §41-42):
он использует те же ``Database`` и ``MigrationRunner``, что и приложение.

Запуск::

    uv run python scripts/init_db.py --config config/config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from monik.config import load_configuration
from monik.domain.errors import MonikError
from monik.infrastructure.db import Database, MigrationRunner


def build_parser() -> argparse.ArgumentParser:
    """Аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="init_db", description="create the Monik database and apply migrations"
    )
    parser.add_argument("--config", default="config/config.yaml", help="configuration file")
    return parser


async def initialise(config_path: str) -> int:
    """Создать базу, применить migrations и проверить целостность."""
    loaded = load_configuration(config_path)
    database = Database(loaded.config.database)
    await database.connect()
    try:
        applied = await MigrationRunner(database).upgrade()
        await database.check_integrity()
        journal = await database.journal_mode()
        foreign_keys = await database.foreign_keys_enabled()
    finally:
        await database.close()

    sys.stdout.write(
        f"database: {loaded.config.database.path}\n"
        f"migrations applied: {', '.join(str(item) for item in applied) or 'none'}\n"
        f"journal mode: {journal}\n"
        f"foreign keys: {'on' if foreign_keys else 'off'}\n"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа скрипта."""
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(initialise(arguments.config))
    except MonikError as error:
        sys.stderr.write(f"init_db: {error.info.code}: {error.info.message}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
