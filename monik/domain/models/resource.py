"""Контракты запроса и результата Resource Manager."""

from __future__ import annotations

from datetime import timedelta
from typing import Self

from pydantic import Field, model_validator

from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority, ResourceResultStatus
from monik.domain.models.base import DomainModel
from monik.domain.value_objects.identifiers import CorrelationId, RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = ["ResourceKey", "ResourceRequest", "ResourceResult"]


class ResourceKey(DomainModel):
    """Идентичность ограниченного ресурса (``12_RESOURCE_MANAGER.md`` §71).

    Лимиты иерархичны: provider, provider+network, provider+network+operation
    (``12_RESOURCE_MANAGER.md`` §72).

    Владельцем ресурса является не только aggregator: через Resource Manager
    проходят также blockchain RPC, gas и price API, Telegram
    (``01_PROJECT_REQUIREMENTS.md`` §34). Поэтому владелец задаётся либо
    ``ProviderId``, либо стабильным строковым именем ресурса — например
    ``"rpc"`` или ``"telegram"``.
    """

    provider_id: ProviderId | str
    network_id: NetworkId | None = None
    operation: CapabilityOperation | None = None

    def __str__(self) -> str:
        parts = [self._owner_name]
        if self.network_id is not None:
            parts.append(str(self.network_id))
        if self.operation is not None:
            parts.append(self.operation.value)
        return "/".join(parts)

    @property
    def _owner_name(self) -> str:
        """Строковое имя владельца ресурса."""
        return (
            self.provider_id.value if isinstance(self.provider_id, ProviderId) else self.provider_id
        )

    def parents(self) -> tuple[ResourceKey, ...]:
        """Родительские ключи от общего к частному (без самого себя)."""
        keys: list[ResourceKey] = [ResourceKey(provider_id=self.provider_id)]
        if self.network_id is not None:
            keys.append(ResourceKey(provider_id=self.provider_id, network_id=self.network_id))
        return tuple(key for key in keys if key != self)


class ResourceRequest(DomainModel):
    """Запрос к внешнему ресурсу (``36_DATA_MODELS.md`` §55).

    Все внешние запросы проходят через Resource Manager
    (``CLAUDE.md`` §14): обход запрещён.

    ``deduplication_key`` позволяет объединять одинаковые одновременные
    запросы (``12_RESOURCE_MANAGER.md`` §45), не меняя их семантику
    (``12_RESOURCE_MANAGER.md`` §46).
    """

    request_id: RequestId
    key: ResourceKey
    priority: RequestPriority
    timeout: timedelta
    created_at: UtcDatetime
    sequence: int = Field(ge=0)
    correlation_id: CorrelationId | None = None
    deduplication_key: str | None = Field(default=None, max_length=256)
    batch_units: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.timeout <= timedelta(0):
            raise ValueError("resource request timeout must be positive")
        return self

    @property
    def ordering_key(self) -> tuple[int, UtcDatetime, int]:
        """Ключ упорядочивания очереди.

        Сначала приоритет, затем время постановки и sequence
        (``04_SCHEDULER.md`` §25). Прибыльность в упорядочивании не участвует
        (``04_SCHEDULER.md`` §26).
        """
        return (self.priority.rank, self.created_at, self.sequence)


class ResourceResult(DomainModel):
    """Итог выполнения запроса (``36_DATA_MODELS.md`` §56).

    Различие статусов обязательно: rate limit и timeout не являются признаком
    неприбыльности или отсутствия поддержки
    (``11_LEVEL_2_SCANNER.md`` §53-55, ``06_AGGREGATOR_ADAPTERS.md`` §76-77).
    """

    request_id: RequestId
    status: ResourceResultStatus
    queued_for: timedelta
    executed_for: timedelta
    attempts: int = Field(default=1, ge=1)
    finished_at: UtcDatetime
    error_code: str | None = Field(default=None, max_length=128)
    retry_after: timedelta | None = None

    @property
    def total_latency(self) -> timedelta:
        """Полная задержка: ожидание в очереди плюс исполнение."""
        return self.queued_for + self.executed_for
