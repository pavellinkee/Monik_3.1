"""Интерфейс хранилища циклов Level 1."""

from __future__ import annotations

from typing import Protocol

from monik.domain.models.scan import Scan
from monik.domain.value_objects.identifiers import ScanId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["ScanRepository"]


class ScanRepository(Protocol):
    """Persistence циклов Level 1 (``38_INTERFACES.md`` §72)."""

    async def create(self, scan: Scan) -> None:
        """Сохранить новый цикл."""
        ...

    async def update(self, scan: Scan) -> None:
        """Обновить состояние цикла."""
        ...

    async def get(self, scan_id: ScanId) -> Scan | None:
        """Найти цикл по идентификатору."""
        ...

    async def recent(self, *, limit: int) -> tuple[Scan, ...]:
        """Последние циклы, начиная с самого свежего."""
        ...

    async def delete_finished_before(self, moment: UtcDatetime) -> int:
        """Удалить завершённые циклы старше указанного момента."""
        ...
