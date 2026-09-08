"""Health Monitoring.

Health описывает доступность подсистем и провайдеров и **не изменяет**
бизнес-состояние (``19_HEALTH_MONITORING.md`` §54-56).
"""

from monik.services.health.monitor import CRITICAL_COMPONENTS, HealthMonitor

__all__ = ["CRITICAL_COMPONENTS", "HealthMonitor"]
