"""Нормализованный маршрут обмена и его отпечаток."""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from monik.domain.enums.operations import OperationType, RoutingMode
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.fingerprints import RouteFingerprint, compute_fingerprint
from monik.domain.value_objects.identity import NetworkId

__all__ = ["Route", "RouteStep"]


class RouteStep(DomainModel):
    """Отдельный этап маршрута (``36_DATA_MODELS.md`` §17).

    Provider-specific формат обязан быть преобразован Adapter'ом в этот вид;
    маршрут не хранится как произвольная строка
    (``06_AGGREGATOR_ADAPTERS.md`` §23).
    """

    input_token: TokenKey
    output_token: TokenKey
    protocol: str = Field(min_length=1, max_length=128)
    pool_address: str | None = Field(default=None, max_length=128)
    share_bps: int | None = Field(default=None, ge=0, le=10_000)

    def fingerprint_payload(self) -> dict[str, Any]:
        """Данные шага, участвующие в вычислении отпечатка."""
        return {
            "input_token": str(self.input_token),
            "output_token": str(self.output_token),
            "protocol": self.protocol,
            "pool_address": self.pool_address,
            "share_bps": self.share_bps,
        }


class Route(DomainModel):
    """Нормализованный маршрут одной операции (``36_DATA_MODELS.md`` §16).

    Маршрут выбирается Level 1 и является immutable для Level 2
    (``10_LEVEL_1_SCANNER.md`` §26, ``11_LEVEL_2_SCANNER.md`` §5).

    ``provider_parameters`` содержит нормализованные параметры, необходимые
    Adapter'у для повторного воспроизведения маршрута
    (``06_AGGREGATOR_ADAPTERS.md`` §24). Секреты в них не помещаются.
    """

    provider_id: ProviderId
    network_id: NetworkId
    operation: OperationType
    routing_mode: RoutingMode
    input_token: TokenKey
    output_token: TokenKey
    steps: tuple[RouteStep, ...] = ()
    provider_parameters: tuple[tuple[str, str], ...] = ()

    @model_validator(mode="after")
    def _validate_consistency(self) -> Self:
        """Маршрут обязан относиться к одной сети и быть связным."""
        if self.input_token.network_id != self.network_id:
            raise ValueError("route input token belongs to a different network")
        if self.output_token.network_id != self.network_id:
            raise ValueError("route output token belongs to a different network")
        if self.input_token == self.output_token:
            raise ValueError("route input and output tokens must differ")
        if not self.steps:
            return self
        if self.steps[0].input_token != self.input_token:
            raise ValueError("first route step must start from the route input token")
        if self.steps[-1].output_token != self.output_token:
            raise ValueError("last route step must end at the route output token")
        for previous, current in zip(self.steps, self.steps[1:], strict=False):
            if previous.output_token != current.input_token:
                raise ValueError("route steps are not connected")
        for step in self.steps:
            if step.input_token.network_id != self.network_id:
                raise ValueError("route step belongs to a different network")
            if step.output_token.network_id != self.network_id:
                raise ValueError("route step belongs to a different network")
        return self

    @property
    def fingerprint(self) -> RouteFingerprint:
        """Детерминированный отпечаток маршрута.

        Зависит только от существенных параметров: провайдера, сети, операции,
        routing mode, токенов, шагов и provider parameters. Timestamps и
        случайные идентификаторы не участвуют (``36_DATA_MODELS.md`` §18).
        """
        payload: dict[str, Any] = {
            "provider_id": self.provider_id.value,
            "network_id": str(self.network_id),
            "operation": self.operation.value,
            "routing_mode": self.routing_mode.value,
            "input_token": str(self.input_token),
            "output_token": str(self.output_token),
            "steps": [step.fingerprint_payload() for step in self.steps],
            "provider_parameters": sorted(self.provider_parameters),
        }
        return RouteFingerprint(compute_fingerprint(payload))

    def matches(self, other: Route) -> bool:
        """Совпадает ли маршрут с другим по отпечатку.

        Используется Level 2 для fixed-route validation
        (``11_LEVEL_2_SCANNER.md`` §18-19).
        """
        return self.fingerprint == other.fingerprint
