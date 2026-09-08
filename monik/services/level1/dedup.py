"""Дедупликация Opportunity внутри цикла и окна времени.

Одинаковые возможности не должны бесконтрольно создавать множество Level 2
Jobs (``02_LEVEL1_SCANNER.md`` §42, ``10_LEVEL_1_SCANNER.md`` §52).
Отпечаток детерминирован и не зависит от случайного идентификатора
(``10_LEVEL_1_SCANNER.md`` §53), поэтому пригоден и для окна дедупликации
(``02_LEVEL1_SCANNER.md`` §44).
"""

from __future__ import annotations

from datetime import timedelta

from monik.domain.value_objects.fingerprints import OpportunityFingerprint
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.services.level1.ports import OpportunityStore

__all__ = ["DeduplicationGuard"]


class DeduplicationGuard:
    """Отсекает повторные возможности внутри цикла и окна."""

    def __init__(
        self,
        store: OpportunityStore,
        *,
        window: timedelta,
    ) -> None:
        self._store = store
        self._window = window
        self._seen: set[str] = set()
        self.duplicates = 0

    async def is_duplicate(self, fingerprint: OpportunityFingerprint, *, now: UtcDatetime) -> bool:
        """Является ли возможность повтором уже известной."""
        key = str(fingerprint)
        if key in self._seen:
            self.duplicates += 1
            return True
        if self._window > timedelta(0):
            existing = await self._store.find_recent_by_fingerprint(
                fingerprint, since=now - self._window
            )
            if existing is not None:
                self._seen.add(key)
                self.duplicates += 1
                return True
        return False

    def remember(self, fingerprint: OpportunityFingerprint) -> None:
        """Запомнить созданную возможность."""
        self._seen.add(str(fingerprint))
