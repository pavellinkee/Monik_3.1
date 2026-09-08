"""Fee System — единая точка получения нормализованных комиссий.

Scanner не реализует provider-specific fee logic
(``01_PROJECT_REQUIREMENTS.md`` §30): Level 1 и Level 2 запрашивают
нормализованные комиссии здесь.

Свежие данные переиспользуются: одинаковый запрос не выполняется при каждом
цикле (``01_PROJECT_REQUIREMENTS.md`` §31, ``07_FEE_SYSTEM.md`` §43).
Одновременные одинаковые запросы объединяются
(``07_FEE_SYSTEM.md`` §60).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from monik.config.sections.fees import FeeConfig
from monik.domain.enums.providers import ProviderId
from monik.domain.models.fee import Fee, FeeSnapshot
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.repositories.sqlite.fees import SqliteFeeRepository
from monik.services.fees.context import FeeContext
from monik.services.fees.policy import FeePolicy, UnknownFeePolicy
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields
from monik.services.resources.dedup import InFlightRegistry

__all__ = ["FeeService"]

_LOGGER = get_logger("services.fees")

#: Версия правил комиссий. Изменение правил обязано увеличивать версию,
#: чтобы исторические снимки интерпретировались корректно
#: (``07_FEE_SYSTEM.md`` §27).
FEE_RULES_VERSION = 1


class FeeService:
    """Нормализует, кэширует и сохраняет комиссии.

    Сервис не рассчитывает прибыльность и не принимает решений
    о подтверждении (``07_FEE_SYSTEM.md`` §82): он только предоставляет
    достоверные данные о стоимости.
    """

    def __init__(
        self,
        config: FeeConfig,
        clock: Clock,
        *,
        policies: dict[ProviderId, FeePolicy],
        repository: SqliteFeeRepository | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._policies = dict(policies)
        self._repository = repository
        self._cache: dict[str, FeeSnapshot] = {}
        self._dedup = InFlightRegistry()

    @property
    def merged_requests(self) -> int:
        """Сколько одновременных одинаковых запросов было объединено."""
        return self._dedup.merged_count

    def register_policy(self, policy: FeePolicy) -> None:
        """Зарегистрировать правила комиссий провайдера."""
        self._policies[policy.provider_id] = policy

    async def fees_for(self, context: FeeContext) -> tuple[Fee, ...]:
        """Актуальные компоненты стоимости для контекста.

        Возвращает свежий снимок из кэша либо формирует новый. Неизвестная
        комиссия возвращается со статусом ``UNKNOWN`` и без суммы.
        """
        snapshot = await self.snapshot_for(context)
        return snapshot.fees

    async def snapshot_for(self, context: FeeContext) -> FeeSnapshot:
        """Снимок комиссий контекста с учётом свежести."""
        cached = self._cache.get(context.cache_key())
        if cached is not None and self._is_fresh(cached):
            return cached
        return await self._dedup.run(
            f"fees:{context.cache_key()}", lambda: self._build_snapshot(context)
        )

    def invalidate(self, context: FeeContext | None = None) -> None:
        """Сбросить кэш целиком или для одного контекста."""
        if context is None:
            self._cache.clear()
            return
        self._cache.pop(context.cache_key(), None)

    async def refresh(self, contexts: tuple[FeeContext, ...]) -> tuple[FeeSnapshot, ...]:
        """Обновить набор контекстов одной операцией.

        Используется startup- и scheduled-обновлением
        (``07_FEE_SYSTEM.md`` §21-22). Контексты группируются, чтобы не
        выполнять одинаковую работу дважды (``07_FEE_SYSTEM.md`` §33).
        """
        unique: dict[str, FeeContext] = {}
        for context in contexts:
            unique.setdefault(context.cache_key(), context)
        snapshots: list[FeeSnapshot] = []
        for context in unique.values():
            self.invalidate(context)
            snapshots.append(await self.snapshot_for(context))
        _LOGGER.info(
            "fee snapshots refreshed",
            extra=log_fields(requested=len(contexts), unique=len(unique)),
        )
        return tuple(snapshots)

    # --- внутреннее --------------------------------------------------------

    def _is_fresh(self, snapshot: FeeSnapshot) -> bool:
        """Свежесть определяется policy, а не только наличием времени."""
        age = self._clock.now() - snapshot.created_at
        return age <= timedelta(seconds=self._config.freshness_seconds)

    async def _build_snapshot(self, context: FeeContext) -> FeeSnapshot:
        """Сформировать и сохранить новый снимок."""
        now = self._clock.now()
        policy = self._policies.get(context.provider_id)
        if policy is None:
            fees = self._unknown_components(context, now)
        else:
            fees = policy.components(context, observed_at=now)
        snapshot = FeeSnapshot(
            snapshot_id=str(uuid.uuid4()),
            provider_id=context.provider_id,
            network_id=context.network_id,
            operation=context.operation,
            fees=fees,
            version=FEE_RULES_VERSION,
            created_at=now,
        )
        self._cache[context.cache_key()] = snapshot
        if self._repository is not None:
            await self._repository.save(snapshot)
        return snapshot

    @staticmethod
    def _unknown_components(context: FeeContext, now: UtcDatetime) -> tuple[Fee, ...]:
        """Компоненты для провайдера без зарегистрированных правил.

        Отсутствие policy не означает отсутствие комиссии: возвращается
        ``UNKNOWN`` (``07_FEE_SYSTEM.md`` §15).
        """
        fallback = UnknownFeePolicy(
            context.provider_id,
            source="fee_service",
            reason="no fee policy registered for this provider",
        )
        return fallback.components(context, observed_at=now)
