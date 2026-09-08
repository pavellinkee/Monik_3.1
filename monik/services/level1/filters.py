"""Фильтрация комбинаций до отправки внешних запросов.

Заведомо неподдерживаемые комбинации не должны попадать во внешний API
(``10_LEVEL_1_SCANNER.md`` §15, ``02_LEVEL1_SCANNER.md`` §76). При этом
``UNKNOWN`` не приравнивается к ``UNSUPPORTED``
(``10_LEVEL_1_SCANNER.md`` §16): runtime-проверка допускается, если это
разрешено конфигурацией.

Полный capability discovery перед каждым scan запрещён
(``10_LEVEL_1_SCANNER.md`` §94.7): здесь выполняется только чтение реестра.
"""

from __future__ import annotations

from monik.config.sections.scanner import Level1Config
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.token import Token
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.services.registries.capabilities import CapabilityRegistry

__all__ = ["CombinationFilter", "capability_operation"]

#: Отображение направления обмена в проверяемую capability.
_OPERATIONS: dict[OperationType, CapabilityOperation] = {
    OperationType.BUY: CapabilityOperation.QUOTE_BUY,
    OperationType.SELL: CapabilityOperation.QUOTE_SELL,
}


def capability_operation(operation: OperationType) -> CapabilityOperation:
    """Capability, соответствующая направлению обмена."""
    return _OPERATIONS[operation]


class CombinationFilter:
    """Решает, стоит ли отправлять запрос для комбинации."""

    def __init__(
        self,
        capabilities: CapabilityRegistry,
        config: Level1Config,
    ) -> None:
        self._capabilities = capabilities
        self._config = config

    def allows(
        self,
        adapter: AggregatorAdapter,
        *,
        network_id: NetworkId,
        operation: OperationType,
        token: Token,
    ) -> bool:
        """Допустима ли комбинация провайдер/сеть/операция/токен."""
        declared = adapter.capabilities
        if not declared.supports_network(network_id):
            return False
        if not declared.supports_operation(operation):
            return False

        key = self._capabilities.key(
            adapter.provider_id,
            network_id,
            capability_operation(operation),
            token.key,
        )
        if not self._capabilities.allows_request(key):
            return False
        status = self._capabilities.status(key)
        if status is CapabilityStatus.SUPPORTED:
            return True
        # UNKNOWN и STALE подтверждением поддержки не являются: запрос
        # выполняется только если policy разрешает runtime-проверку.
        return self._config.allow_unknown_capability

    def provider_pairs(
        self,
        providers: tuple[ProviderId, ...],
        allowed: tuple[tuple[ProviderId, ProviderId], ...],
    ) -> tuple[tuple[ProviderId, ProviderId], ...]:
        """Разрешённые пары «BUY провайдер — SELL провайдер» внутри scope."""
        available = set(providers)
        return tuple(pair for pair in allowed if pair[0] in available and pair[1] in available)
