"""Health Monitoring.

Health описывает **доступность**, а не бизнес-результат
(``19_HEALTH_MONITORING.md`` §54-56):

* health ≠ profitability: здоровый провайдер не означает выгодную котировку;
* health ≠ capability: здоровый провайдер не означает поддержку конкретной
  комбинации токен/сеть/маршрут;
* health не изменяет бизнес-состояние — он его только описывает.

Гистерезис между порогами отказа и восстановления защищает от постоянного
переключения состояний из-за единичных transient ошибок (§49-52).
"""

from __future__ import annotations

from monik.config.sections.health import HealthConfig
from monik.domain.enums.health import ApplicationHealthStatus, ProviderHealthStatus
from monik.domain.enums.providers import ProviderId
from monik.domain.models.health import ApplicationHealth, ComponentHealth, ProviderHealth
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["CRITICAL_COMPONENTS", "HealthMonitor"]

_LOGGER = get_logger("services.health")

#: Подсистемы, критические для основной работы
#: (``19_HEALTH_MONITORING.md`` §10).
CRITICAL_COMPONENTS = frozenset(
    {
        "configuration",
        "database",
        "resource_manager",
        "scheduler",
        "level1",
        "level2",
        "fees",
        "calculator",
        "notifications",
    }
)


class HealthMonitor:
    """Хранит и агрегирует состояние подсистем и провайдеров."""

    def __init__(self, config: HealthConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self._components: dict[str, ComponentHealth] = {}
        self._providers: dict[ProviderId, ProviderHealth] = {}
        self._stopping = False

    # --- подсистемы -------------------------------------------------------

    def set_component(
        self,
        component: str,
        status: ApplicationHealthStatus,
        *,
        reason: str | None = None,
    ) -> ComponentHealth:
        """Зафиксировать состояние подсистемы."""
        health = ComponentHealth(
            component=component,
            status=status,
            observed_at=self._clock.now(),
            reason=reason,
        )
        previous = self._components.get(component)
        self._components[component] = health
        if previous is None or previous.status is not status:
            _LOGGER.info(
                "component health changed",
                extra=log_fields(component=component, status=status.value, reason=reason),
            )
        return health

    def component(self, component: str) -> ComponentHealth | None:
        """Состояние подсистемы."""
        return self._components.get(component)

    def mark_stopping(self) -> None:
        """Перевести приложение в ``STOPPING`` (``19`` §8)."""
        self._stopping = True

    # --- провайдеры -------------------------------------------------------

    def provider(self, provider_id: ProviderId) -> ProviderHealth:
        """Состояние провайдера.

        Отсутствие наблюдений — ``UNKNOWN``, а не ``HEALTHY``
        (``35_STATE_MACHINES.md`` §92).
        """
        known = self._providers.get(provider_id)
        if known is not None:
            return known
        return ProviderHealth(
            provider_id=provider_id,
            status=ProviderHealthStatus.UNKNOWN,
            observed_at=self._clock.now(),
        )

    def record_provider_success(self, provider_id: ProviderId) -> ProviderHealth:
        """Учесть успешное обращение к провайдеру."""
        current = self.provider(provider_id)
        successes = current.consecutive_successes + 1
        status = self._status_after_success(current.status, successes)
        return self._store(
            ProviderHealth(
                provider_id=provider_id,
                status=status,
                observed_at=self._clock.now(),
                consecutive_failures=0,
                consecutive_successes=successes,
            )
        )

    def record_provider_failure(
        self, provider_id: ProviderId, *, reason: str | None = None
    ) -> ProviderHealth:
        """Учесть неудачное обращение к провайдеру."""
        current = self.provider(provider_id)
        failures = current.consecutive_failures + 1
        status = self._status_after_failure(current.status, failures)
        return self._store(
            ProviderHealth(
                provider_id=provider_id,
                status=status,
                observed_at=self._clock.now(),
                consecutive_failures=failures,
                consecutive_successes=0,
                reason=reason,
            )
        )

    def providers(self) -> tuple[ProviderHealth, ...]:
        """Состояние всех наблюдаемых провайдеров."""
        return tuple(self._providers.values())

    def usable_providers(self) -> tuple[ProviderId, ...]:
        """Провайдеры, к которым имеет смысл обращаться.

        ``UNKNOWN`` допускает попытку: отсутствие наблюдений не является
        доказательством недоступности.
        """
        return tuple(
            provider_id
            for provider_id, health in self._providers.items()
            if health.status is not ProviderHealthStatus.UNAVAILABLE
        )

    # --- сводное состояние ------------------------------------------------

    def application_health(self) -> ApplicationHealth:
        """Сводное состояние приложения (``19_HEALTH_MONITORING.md`` §9).

        Определяется состоянием критических подсистем и не может задаваться
        одним провайдером (§9, §12).
        """
        components = tuple(self._components.values())
        providers = self.providers()
        return ApplicationHealth(
            status=self._application_status(components, providers),
            observed_at=self._clock.now(),
            components=components,
            providers=providers,
        )

    def _application_status(
        self,
        components: tuple[ComponentHealth, ...],
        providers: tuple[ProviderHealth, ...],
    ) -> ApplicationHealthStatus:
        if self._stopping:
            return ApplicationHealthStatus.STOPPING
        critical = [item for item in components if item.component in CRITICAL_COMPONENTS]
        if any(item.status is ApplicationHealthStatus.UNAVAILABLE for item in critical):
            return ApplicationHealthStatus.UNAVAILABLE
        if providers and all(
            health.status is ProviderHealthStatus.UNAVAILABLE for health in providers
        ):
            # Все необходимые провайдеры недоступны (§13).
            return ApplicationHealthStatus.DEGRADED
        if any(item.status is ApplicationHealthStatus.DEGRADED for item in components):
            return ApplicationHealthStatus.DEGRADED
        if any(
            health.status in {ProviderHealthStatus.DEGRADED, ProviderHealthStatus.UNAVAILABLE}
            for health in providers
        ):
            # Недоступность одного провайдера не делает приложение
            # недоступным, пока остальные работают (§12).
            return ApplicationHealthStatus.DEGRADED
        if any(item.status is ApplicationHealthStatus.STARTING for item in critical):
            return ApplicationHealthStatus.STARTING
        if not critical:
            return ApplicationHealthStatus.STARTING
        return ApplicationHealthStatus.HEALTHY

    # --- переходы состояний провайдера ------------------------------------

    def _status_after_failure(
        self, current: ProviderHealthStatus, failures: int
    ) -> ProviderHealthStatus:
        """Переход при отказе с учётом порогов (§50, §52)."""
        if failures >= self._config.provider_failure_threshold:
            return ProviderHealthStatus.UNAVAILABLE
        if failures >= self._config.provider_degraded_threshold:
            return ProviderHealthStatus.DEGRADED
        # Единичный сбой не меняет состояние: это защита от flapping (§49).
        return current

    def _status_after_success(
        self, current: ProviderHealthStatus, successes: int
    ) -> ProviderHealthStatus:
        """Переход при успехе с учётом порога восстановления (§51)."""
        if successes >= self._config.provider_recovery_threshold:
            return ProviderHealthStatus.HEALTHY
        if current is ProviderHealthStatus.UNAVAILABLE:
            return ProviderHealthStatus.RECOVERING
        if current is ProviderHealthStatus.UNKNOWN:
            return ProviderHealthStatus.RECOVERING
        return current

    def _store(self, health: ProviderHealth) -> ProviderHealth:
        previous = self._providers.get(health.provider_id)
        self._providers[health.provider_id] = health
        if previous is None or previous.status is not health.status:
            _LOGGER.info(
                "provider health changed",
                extra=log_fields(provider=health.provider_id.value, status=health.status.value),
            )
        return health
