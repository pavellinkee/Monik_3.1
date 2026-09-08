"""Контекст, определяющий применимость комиссии.

Fee Key должен учитывать существенные параметры, но не обобщаться
чрезмерно (``07_FEE_SYSTEM.md`` §45-46): комиссия, зависящая от маршрута
или токена, обязана включать соответствующий контекст, иначе значения
разных контекстов смешаются.
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.fees import FeeType
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.fee import FeeKey
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.fingerprints import RouteFingerprint
from monik.domain.value_objects.identity import NetworkId

__all__ = ["FeeContext"]


@dataclass(frozen=True, slots=True)
class FeeContext:
    """Контекст запроса комиссий для одной операции."""

    provider_id: ProviderId
    network_id: NetworkId
    operation: OperationType
    input_token: TokenKey
    output_token: TokenKey
    input_amount: TokenAmount
    route_fingerprint: RouteFingerprint | None = None

    def key(self, *, fee_type_token: TokenKey | None = None) -> FeeKey:
        """Ключ комиссии для этого контекста."""
        return FeeKey(
            provider_id=self.provider_id,
            network_id=self.network_id,
            operation=self.operation,
            fee_type=FeeType.AGGREGATOR,
            token=fee_type_token or self.input_token,
            route_fingerprint=str(self.route_fingerprint) if self.route_fingerprint else None,
        )

    def cache_key(self) -> str:
        """Строковый ключ для дедупликации и кэширования снимков."""
        route = str(self.route_fingerprint) if self.route_fingerprint else "*"
        return (
            f"{self.provider_id.value}/{self.network_id}/{self.operation.value}/"
            f"{self.input_token}/{self.output_token}/{route}"
        )
