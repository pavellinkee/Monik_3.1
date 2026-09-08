"""Миграции схемы Monik.

Миграции применяются строго последовательно и не могут быть пропущены
(``30_DATABASE_SCHEMA.md`` §16). Новая миграция добавляется отдельным
модулем и регистрируется в :data:`ALL_MIGRATIONS`.
"""

from monik.infrastructure.db.migrations.base import Migration
from monik.infrastructure.db.migrations.m0001_initial import MIGRATION as MIGRATION_0001
from monik.infrastructure.db.migrations.m0002_snapshots import MIGRATION as MIGRATION_0002

#: Все миграции в порядке применения.
ALL_MIGRATIONS: tuple[Migration, ...] = (MIGRATION_0001, MIGRATION_0002)

__all__ = ["ALL_MIGRATIONS", "Migration"]
