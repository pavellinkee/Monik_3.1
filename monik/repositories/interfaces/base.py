"""Общие правила repository layer.

Repository отвечает за persistence и retrieval и **не принимает бизнес-решений**
(``38_INTERFACES.md`` §75, ``39_IMPLEMENTATION_PLAN.md`` §14): он не решает,
прибыльна ли возможность, какой маршрут лучше и нужно ли отправлять
уведомление.

Database models могут отличаться от domain models; преобразование выполняет
repository (``30_DATABASE_SCHEMA.md`` §7).
"""

from __future__ import annotations

__all__: list[str] = []
