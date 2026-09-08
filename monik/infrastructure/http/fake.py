"""Тестовая реализация HTTP-клиента.

**Test implementation, не production** (``CLAUDE.md`` §10, §46,
``39_IMPLEMENTATION_PLAN.md`` §69). Используется в unit-, component- и
integration-тестах, чтобы не обращаться к внешним API
(``23_TESTING.md`` §12).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from monik.domain.errors import MonikError
from monik.infrastructure.http.models import HttpRequest, HttpResponse

__all__ = ["FakeHttpClient", "RecordedCall"]

#: Обработчик, который решает, чем ответить на конкретный запрос.
Handler = Callable[[HttpRequest], HttpResponse | MonikError]


class RecordedCall:
    """Зафиксированный вызов клиента."""

    __slots__ = ("request",)

    def __init__(self, request: HttpRequest) -> None:
        self.request = request


class FakeHttpClient:
    """Детерминированный клиент для тестов.

    Позволяет задать последовательность ответов и инъекцию ошибок, включая
    таймауты и rate limit, не выполняя реальных сетевых вызовов.
    """

    def __init__(
        self,
        responses: Sequence[HttpResponse | MonikError] | None = None,
        *,
        handler: Handler | None = None,
    ) -> None:
        self._queue: list[HttpResponse | MonikError] = list(responses or ())
        self._handler = handler
        self.calls: list[RecordedCall] = []
        self.closed = False

    async def send(self, request: HttpRequest) -> HttpResponse:
        """Вернуть заранее заданный ответ или возбудить заданную ошибку."""
        self.calls.append(RecordedCall(request))
        if self._handler is not None:
            outcome = self._handler(request)
        elif self._queue:
            outcome = self._queue.pop(0)
        else:
            raise AssertionError(f"FakeHttpClient has no response for {request.url}")
        if isinstance(outcome, MonikError):
            raise outcome
        return outcome

    async def aclose(self) -> None:
        """Отметить клиент закрытым."""
        self.closed = True

    @property
    def call_count(self) -> int:
        """Сколько запросов было выполнено."""
        return len(self.calls)

    def last_request(self) -> HttpRequest:
        """Последний выполненный запрос."""
        if not self.calls:
            raise AssertionError("FakeHttpClient has not been called")
        return self.calls[-1].request
