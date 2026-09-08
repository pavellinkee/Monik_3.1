"""Capability Registry."""

from __future__ import annotations

from datetime import timedelta

from monik.config.sections.capabilities import CapabilityConfig
from monik.domain.enums.capability import CapabilityOperation, CapabilityStatus
from monik.domain.enums.errors import ErrorCategory
from monik.domain.enums.providers import ProviderId
from monik.domain.models.capability import Capability, CapabilityKey
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.identity import NetworkId
from monik.repositories.sqlite.capabilities import SqliteCapabilityRepository
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["CapabilityRegistry"]

_LOGGER = get_logger("services.registries.capabilities")

#: Категории ошибок, которые действительно означают отсутствие поддержки.
#: Timeout, rate limit и 5xx сюда не входят: это временные сбои
#: (``06_AGGREGATOR_ADAPTERS.md`` §75-77).
_UNSUPPORTED_CATEGORIES = frozenset({ErrorCategory.UNSUPPORTED})

#: Категории, которые вообще не влияют на состояние capability.
_NEUTRAL_CATEGORIES = frozenset(
    {
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.RESOURCE,
        ErrorCategory.CANCELLATION,
    }
)


class CapabilityRegistry:
    """Хранит и обновляет информацию о поддержке операций.

    Ключевые правила:

    * ``UNKNOWN`` никогда не считается ``SUPPORTED``
      (``36_DATA_MODELS.md`` §61);
    * discovery выполняется при старте и по расписанию, а не перед каждым
      scan (``08_CAPABILITY_REGISTRY.md`` §3-4);
    * временный сбой не переводит комбинацию в ``UNSUPPORTED``: для этого
      нужен порог подряд идущих отказов
      (``20_CAPABILITY_REGISTRY.md`` §26-28);
    * Circuit Breaker и health состояние **не изменяют** реестр
      (``05_RESOURCE_MANAGER.md`` §11, ``19_HEALTH_MONITORING.md`` §55).

    Ответы на статические запросы берутся из памяти: сетевые вызовы при
    lookup не выполняются (``20_CAPABILITY_REGISTRY.md`` §79).
    """

    def __init__(
        self,
        repository: SqliteCapabilityRepository,
        config: CapabilityConfig,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._config = config
        self._clock = clock
        self._cache: dict[str, Capability] = {}

    async def load(self) -> int:
        """Загрузить сохранённое состояние в память.

        Загруженная capability не считается свежей автоматически: свежесть
        проверяется отдельно (``30_DATABASE_SCHEMA.md`` §51).
        """
        stored = await self._repository.list_all()
        self._cache = {str(item.key): item for item in stored}
        return len(self._cache)

    def get(self, key: CapabilityKey) -> Capability:
        """Текущее состояние capability.

        Отсутствие записи означает ``UNKNOWN``, а не поддержку.
        """
        cached = self._cache.get(str(key))
        if cached is not None:
            return cached
        return Capability(
            key=key,
            status=CapabilityStatus.UNKNOWN,
            checked_at=self._clock.now(),
            source="registry_default",
        )

    def status(self, key: CapabilityKey) -> CapabilityStatus:
        """Статус capability с учётом свежести.

        Просроченная поддержка становится ``STALE``: она не подтверждена
        сейчас, но и не означает отсутствие поддержки
        (``08_CAPABILITY_REGISTRY.md`` §11, §35).
        """
        capability = self.get(key)
        if capability.status is CapabilityStatus.SUPPORTED and not capability.is_fresh(
            self._clock.now()
        ):
            return CapabilityStatus.STALE
        return capability.status

    def allows_request(self, key: CapabilityKey) -> bool:
        """Можно ли отправлять запрос для этой комбинации.

        Явно неподдерживаемые комбинации не запрашиваются
        (``02_LEVEL1_SCANNER.md`` §76). ``UNKNOWN`` и ``STALE`` допускают
        runtime-проверку, если это разрешено конфигурацией
        (``10_LEVEL_1_SCANNER.md`` §16) — при этом ``UNKNOWN`` по-прежнему
        не считается подтверждением поддержки.
        """
        status = self.status(key)
        if status is CapabilityStatus.UNSUPPORTED:
            return False
        if status is CapabilityStatus.SUPPORTED:
            return True
        return self._config.enabled

    def is_confirmed(self, key: CapabilityKey) -> bool:
        """Подтверждена ли поддержка свежими данными."""
        return self.status(key) is CapabilityStatus.SUPPORTED

    async def record_discovery(
        self,
        key: CapabilityKey,
        status: CapabilityStatus,
        *,
        source: str,
        detail: str | None = None,
    ) -> Capability:
        """Зафиксировать результат discovery."""
        now = self._clock.now()
        capability = Capability(
            key=key,
            status=status,
            checked_at=now,
            expires_at=now + timedelta(seconds=self._config.freshness_seconds),
            source=source,
            consecutive_failures=0,
            detail=detail,
        )
        await self._store(capability)
        return capability

    async def record_success(self, key: CapabilityKey, *, source: str = "runtime") -> Capability:
        """Учесть успешную операцию.

        Успех сбрасывает счётчик отказов и подтверждает поддержку.
        """
        now = self._clock.now()
        capability = Capability(
            key=key,
            status=CapabilityStatus.SUPPORTED,
            checked_at=now,
            expires_at=now + timedelta(seconds=self._config.freshness_seconds),
            source=source,
            consecutive_failures=0,
        )
        await self._store(capability)
        return capability

    async def record_failure(
        self,
        key: CapabilityKey,
        category: ErrorCategory,
        *,
        source: str = "runtime",
        detail: str | None = None,
    ) -> Capability:
        """Учесть неуспешную операцию.

        Только явный ``UNSUPPORTED`` от провайдера, повторившийся заданное
        число раз, переводит комбинацию в ``UNSUPPORTED``. Временные сбои
        и rate limit состояние не меняют.
        """
        current = self.get(key)
        if category in _NEUTRAL_CATEGORIES:
            return current

        now = self._clock.now()
        if category not in _UNSUPPORTED_CATEGORIES:
            capability = current.replace(
                status=(
                    CapabilityStatus.DEGRADED
                    if current.status is CapabilityStatus.SUPPORTED
                    else current.status.value
                ),
                checked_at=now,
                detail=detail,
            )
            await self._store(capability)
            return capability

        failures = current.consecutive_failures + 1
        reached = failures >= self._config.failure_threshold
        capability = Capability(
            key=key,
            status=CapabilityStatus.UNSUPPORTED if reached else current.status,
            checked_at=now,
            expires_at=now + timedelta(seconds=self._config.freshness_seconds)
            if reached
            else current.expires_at,
            source=source,
            consecutive_failures=failures,
            detail=detail,
        )
        if reached:
            _LOGGER.warning(
                "capability marked unsupported",
                extra=log_fields(capability=str(key), failures=failures),
            )
        await self._store(capability)
        return capability

    def stale_keys(self) -> tuple[CapabilityKey, ...]:
        """Комбинации, требующие обновления по расписанию."""
        now = self._clock.now()
        return tuple(
            capability.key for capability in self._cache.values() if not capability.is_fresh(now)
        )

    def snapshot(self) -> tuple[Capability, ...]:
        """Текущее состояние всех известных capability."""
        return tuple(self._cache.values())

    def key(
        self,
        provider_id: ProviderId,
        network_id: NetworkId,
        operation: CapabilityOperation,
        token: TokenKey | None = None,
    ) -> CapabilityKey:
        """Построить ключ capability."""
        return CapabilityKey(
            provider_id=provider_id,
            network_id=network_id,
            operation=operation,
            token=token,
        )

    async def _store(self, capability: Capability) -> None:
        self._cache[str(capability.key)] = capability
        await self._repository.upsert(capability)
