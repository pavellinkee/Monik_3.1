"""Resource Manager: единственная точка контроля внешних запросов.

Обход менеджера запрещён (``CLAUDE.md`` §14): concurrency, rate limits,
приоритеты, retry, backoff, jitter, circuit breaker, дедупликация,
backpressure и отмена управляются здесь.
"""

from monik.services.resources.circuit import CircuitBreaker
from monik.services.resources.dedup import InFlightRegistry
from monik.services.resources.gate import PriorityGate
from monik.services.resources.limits import RateLimiter, ResourceLimits
from monik.services.resources.manager import ResourceManager, Sleeper
from monik.services.resources.retry import RetryPolicy

__all__ = [
    "CircuitBreaker",
    "InFlightRegistry",
    "PriorityGate",
    "RateLimiter",
    "ResourceLimits",
    "ResourceManager",
    "RetryPolicy",
    "Sleeper",
]
