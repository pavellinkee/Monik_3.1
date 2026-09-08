"""Общие порты источников стоимости.

Level 1 и Level 2 получают комиссии, gas и курсы одинаково: через Fee
System, Gas System и Conversion Service (``02_LEVEL1_SCANNER.md`` §29-31,
``11_LEVEL_2_SCANNER.md`` §31-36). Ни один из сканеров не реализует
provider-specific fee logic и собственную формулу газа.

Протоколы вынесены в общий модуль, чтобы Level 2 не зависел от Level 1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from monik.domain.models.conversion import ConversionRate
from monik.domain.models.fee import Fee, FeeSnapshot
from monik.domain.models.gas import Gas
from monik.domain.models.token import Token
from monik.domain.value_objects.identity import NetworkId
from monik.services.fees.context import FeeContext

__all__ = ["FeeSnapshotSource", "FeeSource", "GasSource", "RateSource"]


@runtime_checkable
class FeeSource(Protocol):
    """Источник комиссий."""

    async def fees_for(self, context: FeeContext) -> tuple[Fee, ...]:
        """Комиссии, применимые к контексту операции."""
        ...


@runtime_checkable
class FeeSnapshotSource(FeeSource, Protocol):
    """Источник комиссий, умеющий отдавать версионированный снимок.

    Снимок нужен Level 2 для аудита подтверждения
    (``11_LEVEL_2_SCANNER.md`` §65).
    """

    async def snapshot_for(self, context: FeeContext) -> FeeSnapshot:
        """Согласованный снимок комиссий контекста."""
        ...


@runtime_checkable
class GasSource(Protocol):
    """Источник оценки газа."""

    async def estimate(
        self,
        network_id: NetworkId,
        *,
        gas_units: int | None,
        source: str = "gas_estimator",
    ) -> Gas:
        """Стоимость исполнения; при недостатке данных — ``UNKNOWN``."""
        ...


@runtime_checkable
class RateSource(Protocol):
    """Источник курсов конверсии."""

    async def rate(self, from_token: Token, to_token: Token) -> ConversionRate | None:
        """Курс заданного направления или ``None``."""
        ...
