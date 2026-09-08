"""Тесты контролируемого HTTP-клиента."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from monik.config.sections.http import HttpConfig
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    DomainValidationError,
    NetworkError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from monik.infrastructure.http import (
    FakeHttpClient,
    HttpClient,
    HttpRequest,
    HttpResponse,
    HttpxClient,
    UrlPolicy,
    classify_response,
)

POLICY = UrlPolicy({"api.example.com"})
URL = "https://api.example.com/v1/quote"


def _client(handler: object, *, config: HttpConfig | None = None) -> HttpxClient:
    """Клиент с контролируемым транспортом; политика и лимиты — настоящие."""
    return HttpxClient(
        config or HttpConfig(),
        POLICY,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


class TestConfiguration:
    def test_tls_verification_cannot_be_disabled(self) -> None:
        """Отключение TLS verification запрещено (06 §79)."""
        with pytest.raises(ValueError, match="verify_tls"):
            HttpConfig(verify_tls=False)

    def test_redirects_require_explicit_opt_in(self) -> None:
        with pytest.raises(ValueError, match="max_redirects"):
            HttpConfig(follow_redirects=False, max_redirects=3)

    def test_defaults_are_safe(self) -> None:
        config = HttpConfig()
        assert config.verify_tls
        assert not config.follow_redirects
        assert config.max_response_bytes > 0


class TestRequests:
    async def test_successful_request(self) -> None:
        client = _client(lambda request: httpx.Response(200, json={"ok": True}))
        response = await client.send(HttpRequest(method="GET", url=URL))
        assert response.is_success
        assert response.json() == {"ok": True}
        await client.aclose()

    async def test_sends_headers_and_params(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("authorization", "")
            captured["query"] = request.url.query.decode()
            return httpx.Response(200, json={})

        client = _client(handler)
        await client.send(
            HttpRequest(
                method="GET",
                url=URL,
                headers={"authorization": "Bearer token-value"},
                params={"src": "0xabc"},
            )
        )
        assert captured["auth"] == "Bearer token-value"
        assert "src=0xabc" in captured["query"]
        await client.aclose()

    async def test_blocked_url_is_never_requested(self) -> None:
        """Запрос по неразрешённому адресу не выполняется вовсе."""
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            return httpx.Response(200)

        client = _client(handler)
        with pytest.raises(DomainValidationError):
            await client.send(HttpRequest(method="GET", url="https://evil.test/x"))
        assert not called
        await client.aclose()

    async def test_timeout_is_normalized(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        client = _client(handler)
        with pytest.raises(TimeoutError, match="timed out"):
            await client.send(HttpRequest(method="GET", url=URL))
        await client.aclose()

    async def test_transport_error_is_normalized(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        client = _client(handler)
        with pytest.raises(NetworkError, match="transport failure"):
            await client.send(HttpRequest(method="GET", url=URL))
        await client.aclose()

    async def test_oversized_response_is_rejected(self) -> None:
        payload = "x" * 5000
        client = _client(
            lambda request: httpx.Response(200, text=payload),
            config=HttpConfig(max_response_bytes=1024),
        )
        with pytest.raises(DataError, match="exceeds"):
            await client.send(HttpRequest(method="GET", url=URL))
        await client.aclose()

    async def test_redirect_to_disallowed_host_is_rejected(self) -> None:
        """Редирект не может увести на неразрешённый хост."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.example.com":
                return httpx.Response(302, headers={"location": "https://evil.test/x"})
            return httpx.Response(200, json={})

        client = _client(handler, config=HttpConfig(follow_redirects=True, max_redirects=2))
        with pytest.raises(DomainValidationError, match="not in the allowed hosts"):
            await client.send(HttpRequest(method="GET", url=URL))
        await client.aclose()

    async def test_invalid_json_is_data_error(self) -> None:
        client = _client(lambda request: httpx.Response(200, text="not json"))
        response = await client.send(HttpRequest(method="GET", url=URL))
        with pytest.raises(DataError, match="not valid JSON"):
            response.json()
        await client.aclose()

    def test_unsupported_method_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported HTTP method"):
            HttpRequest(method="DELETE", url=URL)


class TestResponseClassification:
    def _response(self, status: int, headers: dict[str, str] | None = None) -> HttpResponse:
        return HttpResponse(status_code=status, text="{}", headers=headers or {})

    def test_success_passes(self) -> None:
        classify_response(self._response(200))

    def test_rate_limit_is_distinct(self) -> None:
        """429 не является обычной ошибкой (11 §55)."""
        with pytest.raises(RateLimitError) as error:
            classify_response(self._response(429, {"retry-after": "30"}))
        assert error.value.info.retry_after == timedelta(seconds=30)

    def test_rate_limit_without_retry_after(self) -> None:
        with pytest.raises(RateLimitError) as error:
            classify_response(self._response(429))
        assert error.value.info.retry_after is None

    def test_invalid_retry_after_is_ignored(self) -> None:
        with pytest.raises(RateLimitError) as error:
            classify_response(self._response(429, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}))
        assert error.value.info.retry_after is None

    @pytest.mark.parametrize("status", [401, 403])
    def test_authentication_errors(self, status: int) -> None:
        with pytest.raises(AuthenticationError):
            classify_response(self._response(status))

    @pytest.mark.parametrize("status", [500, 502, 503])
    def test_server_errors_are_provider_errors(self, status: int) -> None:
        with pytest.raises(ProviderError):
            classify_response(self._response(status))

    @pytest.mark.parametrize("status", [400, 404, 422])
    def test_client_errors_are_data_errors(self, status: int) -> None:
        """Ответ 4xx не исправляется повтором (18 §35)."""
        with pytest.raises(DataError) as error:
            classify_response(self._response(status))
        assert not error.value.is_retryable


class TestFakeHttpClient:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(FakeHttpClient(), HttpClient)

    async def test_returns_queued_responses(self) -> None:
        client = FakeHttpClient([HttpResponse(status_code=200, text='{"a":1}')])
        response = await client.send(HttpRequest(method="GET", url=URL))
        assert response.json() == {"a": 1}
        assert client.call_count == 1

    async def test_raises_injected_error(self) -> None:
        client = FakeHttpClient([TimeoutError("boom")])
        with pytest.raises(TimeoutError):
            await client.send(HttpRequest(method="GET", url=URL))

    async def test_handler_receives_request(self) -> None:
        client = FakeHttpClient(
            handler=lambda request: HttpResponse(status_code=200, text=request.url)
        )
        response = await client.send(HttpRequest(method="GET", url=URL))
        assert response.text == URL
        assert client.last_request().url == URL

    async def test_missing_response_is_an_explicit_failure(self) -> None:
        with pytest.raises(AssertionError, match="no response"):
            await FakeHttpClient().send(HttpRequest(method="GET", url=URL))

    async def test_close_is_recorded(self) -> None:
        client = FakeHttpClient()
        await client.aclose()
        assert client.closed
