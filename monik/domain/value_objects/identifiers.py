"""Идентификаторы сущностей Monik.

Level 1 использует пространство ``#V1234``, Level 2 — ``#K1234``
(``CLAUDE.md`` §20). Это **разные** пространства идентификаторов: совпадение
числовой части ничего не означает.
"""

from __future__ import annotations

import re
import uuid
from typing import Self

from monik.domain.value_objects.strings import ValidatedStr

__all__ = ["CorrelationId", "KId", "OpportunityId", "RequestId", "ScanId", "VId"]

_V_ID_RE = re.compile(r"^#V\d{1,12}$")
_K_ID_RE = re.compile(r"^#K\d{1,12}$")
_UUID_LIKE_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class VId(ValidatedStr):
    """Публичный идентификатор Opportunity (сущности Level 1): ``#V1234``."""

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("#"):
            normalized = "#" + normalized
        if not _V_ID_RE.fullmatch(normalized):
            raise ValueError(f"invalid Level 1 id: {value!r}; expected format '#V1234'")
        return normalized

    @classmethod
    def from_sequence(cls, sequence: int) -> VId:
        """Построить идентификатор из монотонной последовательности."""
        if sequence <= 0:
            raise ValueError(f"sequence must be positive, got {sequence}")
        return cls(f"#V{sequence}")

    @property
    def sequence(self) -> int:
        """Числовая часть идентификатора."""
        return int(self[2:])


class KId(ValidatedStr):
    """Публичный идентификатор Level 2 Job: ``#K1234``.

    Отображается первым в каждом Opportunity notification (``CLAUDE.md`` §35)
    и принимается командой ``/details K1234`` (``CLAUDE.md`` §36).
    """

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("#"):
            normalized = "#" + normalized
        if not _K_ID_RE.fullmatch(normalized):
            raise ValueError(f"invalid Level 2 id: {value!r}; expected format '#K1234'")
        return normalized

    @classmethod
    def from_sequence(cls, sequence: int) -> KId:
        """Построить идентификатор из монотонной последовательности."""
        if sequence <= 0:
            raise ValueError(f"sequence must be positive, got {sequence}")
        return cls(f"#K{sequence}")

    @property
    def sequence(self) -> int:
        """Числовая часть идентификатора."""
        return int(self[2:])


class _UuidId(ValidatedStr):
    """Внутренний идентификатор на основе UUID4."""

    __slots__ = ()

    @classmethod
    def normalize(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _UUID_LIKE_RE.fullmatch(normalized):
            raise ValueError(f"invalid {cls.__name__}: {value!r}; expected uuid4 string")
        return normalized

    @classmethod
    def generate(cls) -> Self:
        """Сгенерировать новый идентификатор."""
        return cls(str(uuid.uuid4()))


class OpportunityId(_UuidId):
    """Внутренний первичный ключ Opportunity.

    Публичное отображение выполняется через :class:`VId`; внутренний ключ
    стабилен и не зависит от нумерации.
    """

    __slots__ = ()


class ScanId(_UuidId):
    """Идентификатор одного цикла Level 1 (``10_LEVEL_1_SCANNER.md`` §56)."""

    __slots__ = ()


class RequestId(_UuidId):
    """Идентификатор одного внешнего запроса (``10_LEVEL_1_SCANNER.md`` §57)."""

    __slots__ = ()


class CorrelationId(_UuidId):
    """Сквозной идентификатор для трассировки workflow (``28_OBSERVABILITY.md``)."""

    __slots__ = ()
