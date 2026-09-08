"""Контролируемый HTTP-клиент.

Единственное место, где Monik работает с HTTP-библиотекой напрямую
(``25_PROJECT_STRUCTURE.md`` §62). Business logic получает абстракцию
:class:`HttpClient`, а не объекты ``httpx``.

Клиент **не** реализует retry и rate limiting: это ответственность
Resource Manager (``38_INTERFACES.md`` §91).
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Protocol, runtime_checkable

import httpx

from monik.config.sections.http import HttpConfig
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    NetworkError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from monik.infrastructure.http.models import HttpRequest, HttpResponse
from monik.infrastructure.http.safety import UrlPolicy

__all__ = ["HttpClient", "HttpxClient", "classify_response"]

#: Заголовок, в котором провайдер сообщает допустимую паузу перед повтором.
_RETRY_AFTER_HEADER = "retry-after"


@runtime_checkable
class HttpClient(Protocol):
    """Абстракция исходящих HTTP-запросов."""

    async def send(self, request: HttpRequest) -> HttpResponse:
        """Выполнить запрос и вернуть нормализованный ответ."""
        ...

    async def aclose(self) -> None:
        """Освободить сетевые ресурсы."""
        ...


class HttpxClient:
    """Реализация :class:`HttpClient` поверх ``httpx``.

    Обеспечивает обязательные гарантии: timeout, проверку TLS, лимит размера
    ответа, контролируемую политику редиректов и allowlist хостов.
    """

    def __init__(
        self,
        config: HttpConfig,
        url_policy: UrlPolicy,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Создать клиент.

        ``transport`` позволяет подставить контролируемый транспорт в тестах,
        не обходя политику URL и лимиты: остальные гарантии остаются теми же.
        """
        self._config = config
        self._policy = url_policy
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(
                connect=config.connect_timeout_seconds,
                read=config.read_timeout_seconds,
                write=config.read_timeout_seconds,
                pool=config.connect_timeout_seconds,
            ),
            verify=config.verify_tls,
            follow_redirects=config.follow_redirects,
            max_redirects=config.max_redirects,
            limits=httpx.Limits(max_connections=config.max_connections),
            headers={"user-agent": config.user_agent},
        )

    async def send(self, request: HttpRequest) -> HttpResponse:
        """Выполнить запрос.

        URL проверяется до отправки: обращение по неразрешённому адресу
        не выполняется вовсе.
        """
        self._policy.validate(request.url)
        timeout = (
            httpx.Timeout(request.timeout_seconds)
            if request.timeout_seconds is not None
            else httpx.USE_CLIENT_DEFAULT
        )
        started = time.monotonic()
        try:
            response = await self._client.request(
                request.method.upper(),
                request.url,
                headers=request.headers or None,
                params=request.params or None,
                json=request.json_body,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"request timed out: {type(exc).__name__}",
                code="http_timeout",
                operation=request.method.upper(),
                request_id=request.request_id,
            ) from exc
        except httpx.TooManyRedirects as exc:
            raise DataError(
                "response exceeded the allowed redirect count",
                code="http_too_many_redirects",
                request_id=request.request_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(
                f"transport failure: {type(exc).__name__}",
                code="http_transport_error",
                operation=request.method.upper(),
                request_id=request.request_id,
            ) from exc

        self._validate_redirect_target(response, request)
        body = self._read_limited(response, request)
        return HttpResponse(
            status_code=response.status_code,
            text=body,
            headers={key.lower(): value for key, value in response.headers.items()},
            request_id=request.request_id,
            # Длительность измеряется монотонными часами: она не зависит от
            # перевода системного времени и доступна для любого транспорта.
            elapsed_seconds=time.monotonic() - started,
        )

    def _validate_redirect_target(self, response: httpx.Response, request: HttpRequest) -> None:
        """Убедиться, что финальный URL остался разрешённым."""
        final_url = str(response.url)
        if final_url != request.url:
            self._policy.validate(final_url)

    def _read_limited(self, response: httpx.Response, request: HttpRequest) -> str:
        """Прочитать тело с учётом лимита размера."""
        content = response.content
        if len(content) > self._config.max_response_bytes:
            raise DataError(
                f"response body exceeds {self._config.max_response_bytes} bytes",
                code="http_response_too_large",
                http_status=response.status_code,
                request_id=request.request_id,
            )
        return content.decode("utf-8", errors="replace")

    async def aclose(self) -> None:
        """Закрыть соединения."""
        await self._client.aclose()


def classify_response(response: HttpResponse, *, provider: str | None = None) -> None:
    """Превратить неуспешный HTTP-статус в нормализованную ошибку.

    Различие категорий обязательно: 429 и 5xx — временные состояния,
    401/403 — ошибка конфигурации credentials, 4xx — ошибка запроса
    (``06_AGGREGATOR_ADAPTERS.md`` §11-12).
    """
    if response.is_success:
        return
    status = response.status_code
    if status == 429:
        raise RateLimitError(
            "provider rate limit reached",
            code="http_rate_limited",
            http_status=status,
            provider_code=provider,
            retry_after=_parse_retry_after(response),
            request_id=response.request_id,
        )
    if status in {401, 403}:
        raise AuthenticationError(
            "provider rejected the credentials",
            code="http_authentication_failed",
            http_status=status,
            provider_code=provider,
            request_id=response.request_id,
        )
    if 500 <= status < 600:
        raise ProviderError(
            f"provider returned server error {status}",
            code="http_server_error",
            http_status=status,
            provider_code=provider,
            request_id=response.request_id,
        )
    raise DataError(
        f"provider rejected the request with status {status}",
        code="http_client_error",
        http_status=status,
        provider_code=provider,
        request_id=response.request_id,
    )


def _parse_retry_after(response: HttpResponse) -> timedelta | None:
    """Разобрать заголовок ``Retry-After``.

    Значение обязательно учитывается retry-политикой (``CLAUDE.md`` §32).
    """
    raw = response.header(_RETRY_AFTER_HEADER)
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if seconds < 0:
        return None
    return timedelta(seconds=seconds)
