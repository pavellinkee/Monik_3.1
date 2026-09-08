"""Колонки для восстановления доменных снимков.

Level 2 обязан сохранять calculation snapshot, позволяющий восстановить,
почему сумма была подтверждена или отклонена
(``11_LEVEL_2_SCANNER.md`` §66-67). Для этого нужны сами котировки, на
которых принято решение.

Котировки сохраняются **только** для проверенных сумм
(``VERIFIED_PROFITABLE`` / ``VERIFIED_UNPROFITABLE``): это подтверждающие
данные конкретного решения, а не полный поток всех Level 2 quotes,
хранение которого запрещено (``11_LEVEL_2_SCANNER.md`` §69,
``30_DATABASE_SCHEMA.md`` §44-45). На эти записи распространяется общая
retention policy.
"""

from __future__ import annotations

from monik.infrastructure.db.migrations.base import Migration

__all__ = ["MIGRATION"]

_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE opportunity_amounts ADD COLUMN preliminary_result_json TEXT NOT NULL DEFAULT '{}'",
    # Decimals промежуточного токена отличаются от decimals входного
    # (например AAVE 18 против USDT 6), поэтому хранятся явно:
    # выводить их из символа или из другой суммы запрещено (01 §10).
    "ALTER TABLE opportunity_amounts ADD COLUMN buy_output_decimals INTEGER NOT NULL DEFAULT 18",
    "ALTER TABLE level2_amount_results ADD COLUMN buy_quote_json TEXT",
    "ALTER TABLE level2_amount_results ADD COLUMN sell_quote_json TEXT",
)

MIGRATION = Migration(version=2, name="confirmation_snapshots", statements=_STATEMENTS)
