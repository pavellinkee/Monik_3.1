"""Repository interfaces (protocols).

Services зависят от этих контрактов, а не от конкретной реализации
(``38_INTERFACES.md`` §67, ``25_PROJECT_STRUCTURE.md`` §57).
"""

from monik.repositories.interfaces.jobs import JobRepository
from monik.repositories.interfaces.opportunities import OpportunityRepository
from monik.repositories.interfaces.scans import ScanRepository
from monik.repositories.interfaces.sequences import IdSequenceRepository

__all__ = [
    "IdSequenceRepository",
    "JobRepository",
    "OpportunityRepository",
    "ScanRepository",
]
