"""Общая основа адаптеров, работающих по HTTP.

Здесь сосредоточена инфраструктурная обвязка, одинаковая для всех
провайдеров: выполнение запроса через Resource Manager, применение
credentials, нормализация HTTP-статусов и таймаутов.

Provider-specific детали (endpoints, параметры, разбор ответа, правила
комиссий) остаются в модуле конкретного адаптера
(``06_AGGREGATOR_ADAPTERS.md`` §3, §27-28).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from monik.config.secrets import SecretValue
from monik.config.sections.providers import ProviderConfig
from monik.domain.enums.capability import CapabilityOperation
from monik.domain.enums.providers import ProviderId
from monik.domain.enums.resources import RequestPriority
from monik.domain.errors import AuthenticationError
from monik.domain.models.resource import ResourceKey, ResourceRequest
from monik.domain.value_objects.identifiers import CorrelationId, RequestId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.http import HttpClient, HttpRequest, HttpResponse, classify_response
from monik.services.observability.clock import Clock
from monik.services.resources import ResourceManager

__all__ = ["HttpProviderAdapter"]


class HttpProviderAdapter:
    """Базовая реализация адаптера поверх HTTP.

    Все внешние вызовы выполняются через Resource Manager
    (``06_AGGREGATOR_ADAPTERS.md`` §31): собственных повторов, очередей и
    ограничений частоты адаптер не создаёт.
    """

    def __init__(
        self,
        provider_id: ProviderId,
        config: ProviderConfig,
        *,
        http: HttpClient,
        resources: ResourceManager,
        clock: Clock,
        api_key: SecretValue | None = None,
        base_url: str,
    ) -> None:
        self._provider_id = provider_id
        self._config = config
        self._http = http
        self._resources = resources
        self._clock = clock
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def provider_id(self) -> ProviderId:
        """Идентификатор провайдера."""
        return self._provider_id

    @property
    def base_url(self) -> str:
        """Базовый URL API."""
        return self._base_url

    async def aclose(self) -> None:
        """Освободить ресурсы HTTP-клиента."""
        await self._http.aclose()

    # --- выполнение запросов ---------------------------------------------

    def auth_headers(self) -> dict[str, str]:
        """Заголовки аутентификации.

        Значение секрета берётся только здесь и не логируется
        (``06_AGGREGATOR_ADAPTERS.md`` §14).
        """
        if self._api_key is None:
            return {}
        return {"Authorization": f"Bearer {self._api_key.get()}"}

    def require_credentials(self) -> SecretValue:
        """Убедиться, что credentials заданы."""
        if self._api_key is None:
            raise AuthenticationError(
                f"{self._provider_id.value} adapter has no credentials configured",
                code="provider_credentials_missing",
                provider_code=self._provider_id.value,
            )
        return self._api_key

    async def request_json(
        self,
        *,
        path: str,
        network_id: NetworkId,
        operation: CapabilityOperation,
        request_id: RequestId,
        method: str = "GET",
        params: dict[str, str] | None = None,
        json_body: Any = None,
        priority: RequestPriority = RequestPriority.LEVEL1_BUY,
        correlation_id: CorrelationId | None = None,
        timeout: timedelta | None = None,
        deduplication_key: str | None = None,
        batch_units: int = 1,
    ) -> Any:
        """Выполнить запрос и вернуть разобранный JSON."""
        response = await self.request(
            path=path,
            network_id=network_id,
            operation=operation,
            request_id=request_id,
            method=method,
            params=params,
            json_body=json_body,
            priority=priority,
            correlation_id=correlation_id,
            timeout=timeout,
            deduplication_key=deduplication_key,
            batch_units=batch_units,
        )
        return response.json()

    async def request(
        self,
        *,
        path: str,
        network_id: NetworkId,
        operation: CapabilityOperation,
        request_id: RequestId,
        method: str = "GET",
        params: dict[str, str] | None = None,
        json_body: Any = None,
        priority: RequestPriority = RequestPriority.LEVEL1_BUY,
        correlation_id: CorrelationId | None = None,
        timeout: timedelta | None = None,
        deduplication_key: str | None = None,
        batch_units: int = 1,
    ) -> HttpResponse:
        """Выполнить запрос через Resource Manager.

        Метод и тело задаются адаптером: одни провайдеры принимают
        параметры в query, другие — в теле POST-запроса.
        """
        url = f"{self._base_url}{path}"
        effective_timeout = timeout or timedelta(seconds=self._config.request_timeout_seconds)
        resource_request = ResourceRequest(
            request_id=request_id,
            key=ResourceKey(
                provider_id=self._provider_id,
                network_id=network_id,
                operation=operation,
            ),
            priority=priority,
            timeout=effective_timeout,
            created_at=self._clock.now(),
            sequence=0,
            correlation_id=correlation_id,
            deduplication_key=deduplication_key,
            batch_units=batch_units,
        )

        async def call() -> HttpResponse:
            response = await self._http.send(
                HttpRequest(
                    method=method,
                    url=url,
                    headers=self.auth_headers(),
                    params=params or {},
                    json_body=json_body,
                    request_id=request_id,
                    timeout_seconds=effective_timeout.total_seconds(),
                )
            )
            classify_response(response, provider=self._provider_id.value)
            return response

        return await self._resources.execute(resource_request, call)
