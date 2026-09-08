"""SQLite connection management, migrations, transactions.

Единственное место, где Monik работает с драйвером SQLite напрямую
(``25_PROJECT_STRUCTURE.md`` §63). Business services используют repository
boundary, а не эти классы.
"""

from monik.infrastructure.db.connection import Database, Transaction
from monik.infrastructure.db.migrations import ALL_MIGRATIONS, Migration
from monik.infrastructure.db.runner import MigrationRunner
from monik.infrastructure.db.transactions import TransactionManager

__all__ = [
    "ALL_MIGRATIONS",
    "Database",
    "Migration",
    "MigrationRunner",
    "Transaction",
    "TransactionManager",
]
