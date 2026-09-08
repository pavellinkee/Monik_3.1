"""Application layer: composition root и жизненный цикл.

Business logic здесь отсутствует (``25_PROJECT_STRUCTURE.md`` §5):
слой только собирает подсистемы и управляет их запуском.
"""

from monik.app.container import Container, Repositories, build_container
from monik.app.lifecycle import Application, build_application, create_application
from monik.app.recovery import RecoveryReport, RecoveryService
from monik.app.supervisor import SupervisedWorker, Supervisor

__all__ = [
    "Application",
    "Container",
    "RecoveryReport",
    "RecoveryService",
    "Repositories",
    "SupervisedWorker",
    "Supervisor",
    "build_application",
    "build_container",
    "create_application",
]
