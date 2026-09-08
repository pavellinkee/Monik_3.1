"""Token / Network / Provider / Capability registries.

Каждый реестр является authoritative источником для своего типа данных;
параллельные источники canonical информации не создаются
(``39_IMPLEMENTATION_PLAN.md`` §17).
"""

from monik.services.registries.capabilities import CapabilityRegistry
from monik.services.registries.networks import NetworkRegistry
from monik.services.registries.providers import ProviderRegistry
from monik.services.registries.tokens import TokenRegistry

__all__ = [
    "CapabilityRegistry",
    "NetworkRegistry",
    "ProviderRegistry",
    "TokenRegistry",
]
