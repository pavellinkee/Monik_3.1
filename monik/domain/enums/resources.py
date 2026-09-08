"""Resource Manager: приоритеты, состояния ресурсов, результаты запросов."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class RequestPriority(DomainEnum):
    """Приоритет запроса к внешнему ресурсу.

    Порядок обслуживания (``CLAUDE.md`` §15, ``05_RESOURCE_MANAGER.md`` §16-20):

    ``LEVEL2`` > ``LEVEL1_SELL`` > ``LEVEL1_BUY`` > ``MAINTENANCE`` > ``BACKGROUND``.

    Прибыльность возможности **не** влияет на приоритет
    (``04_SCHEDULER.md`` §26).
    """

    LEVEL2 = "level2"
    LEVEL1_SELL = "level1_sell"
    LEVEL1_BUY = "level1_buy"
    MAINTENANCE = "maintenance"
    BACKGROUND = "background"

    @property
    def rank(self) -> int:
        """Числовой ранг: меньше — выше приоритет.

        Используется очередью Resource Manager. Внутри одного ранга порядок
        определяется ``created_at`` и sequence number (``04_SCHEDULER.md`` §25).
        """
        return _PRIORITY_RANKS[self]


_PRIORITY_RANKS: dict[RequestPriority, int] = {
    RequestPriority.LEVEL2: 0,
    RequestPriority.LEVEL1_SELL: 1,
    RequestPriority.LEVEL1_BUY: 2,
    RequestPriority.MAINTENANCE: 3,
    RequestPriority.BACKGROUND: 4,
}


class ResourceState(DomainEnum):
    """Состояние ограниченного внешнего ресурса (``05_RESOURCE_MANAGER.md`` §5-10)."""

    AVAILABLE = "available"
    BUSY = "busy"
    RATE_LIMITED = "rate_limited"
    COOLDOWN = "cooldown"
    CIRCUIT_OPEN = "circuit_open"


class CircuitState(DomainEnum):
    """Состояние circuit breaker (``CLAUDE.md`` §33, ``12_RESOURCE_MANAGER.md`` §32-34).

    Circuit breaker отражает временную недоступность и **не изменяет**
    Capability Registry (``05_RESOURCE_MANAGER.md`` §11).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ResourceResultStatus(DomainEnum):
    """Итог выполнения запроса через Resource Manager (``36_DATA_MODELS.md`` §56)."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
