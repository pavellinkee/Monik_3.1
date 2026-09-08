"""Детерминированные отпечатки для сравнения и дедупликации.

Fingerprint обязан зависеть только от существенных параметров и не должен
включать timestamps, случайные идентификаторы или секреты
(``36_DATA_MODELS.md`` §18). Одинаковый логический объект обязан давать
одинаковый fingerprint независимо от порядка полей в исходном ответе API
(``06_AGGREGATOR_ADAPTERS.md`` §83).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from monik.domain.value_objects.strings import ValidatedStr

__all__ = [
    "Fingerprint",
    "NotificationFingerprint",
    "OpportunityFingerprint",
    "RouteFingerprint",
    "compute_fingerprint",
]

_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class Fingerprint(ValidatedStr):
    """Шестнадцатеричный SHA-256 отпечаток."""

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _FINGERPRINT_RE.fullmatch(normalized):
            raise ValueError(f"invalid fingerprint: {value!r}; expected 64 hex chars")
        return normalized


class RouteFingerprint(Fingerprint):
    """Отпечаток нормализованного маршрута.

    Используется Level 2 для проверки того, что провайдер воспроизвёл именно
    зафиксированный Level 1 маршрут (``11_LEVEL_2_SCANNER.md`` §18).
    Изменение существенного параметра маршрута обязано менять отпечаток
    (``06_AGGREGATOR_ADAPTERS.md`` §25).
    """

    __slots__ = ()


class OpportunityFingerprint(Fingerprint):
    """Отпечаток логической Opportunity для дедупликации.

    Учитывает сеть, тройку токенов, пару агрегаторов и отпечатки обоих
    маршрутов (``10_LEVEL_1_SCANNER.md`` §53). Не зависит от случайного
    идентификатора (``04_SCHEDULER.md`` §23).
    """

    __slots__ = ()


class NotificationFingerprint(Fingerprint):
    """Отпечаток logical notification: ``opportunity + destination``.

    Обеспечивает идемпотентность доставки (``15_NOTIFICATION_SYSTEM.md`` §19,
    ``30_DATABASE_SCHEMA.md`` §41).
    """

    __slots__ = ()


def _canonical(value: Any) -> Any:
    """Привести структуру к детерминированному виду перед сериализацией."""
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        raise ValueError("float is not allowed in fingerprint input; use Decimal or str")
    if isinstance(value, str | int | bool) or value is None:
        return value
    return str(value)


def compute_fingerprint(payload: dict[str, Any]) -> str:
    """Вычислить детерминированный SHA-256 отпечаток структуры.

    Сортировка ключей на всех уровнях делает результат независимым от порядка
    полей. ``float`` отклоняется: его текстовое представление не гарантирует
    детерминизма и запрещён архитектурой для финансовых данных.
    """
    canonical = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
