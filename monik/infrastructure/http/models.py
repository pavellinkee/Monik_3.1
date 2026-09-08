"""Контракты HTTP-запроса и ответа.

Business logic не получает объекты используемой HTTP-библиотеки
(``38_INTERFACES.md`` §38): наружу отдаются только эти модели.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from monik.domain.errors import DataError
from monik.domain.value_objects.identifiers import RequestId

__all__ = ["HttpRequest", "HttpResponse"]


@dataclass(frozen=True, slots=True)
class HttpRequest:
    """Описание исходящего запроса.

    Заголовки с секретами формируются Adapter'ом и не логируются
    (``06_AGGREGATOR_ADAPTERS.md`` §66).
    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    json_body: Any = None
    request_id: RequestId | None = None
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.method.upper() not in {"GET", "POST"}:
            raise ValueError(f"unsupported HTTP method: {self.method}")


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Нормализованный ответ.

    Тело хранится как текст: разбор выполняет Adapter, который знает формат
    конкретного провайдера.
    """

    status_code: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)
    request_id: RequestId | None = None
    elapsed_seconds: float = 0.0

    @property
    def is_success(self) -> bool:
        """Успешен ли ответ по HTTP-статусу."""
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        """Разобрать тело как JSON.

        Некорректный JSON — ошибка данных: повтор запроса не исправит
        содержимое ответа (``06_AGGREGATOR_ADAPTERS.md`` §10).
        """
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise DataError(
                f"response body is not valid JSON: {exc.msg}",
                code="invalid_json_response",
                http_status=self.status_code,
            ) from exc

    def header(self, name: str) -> str | None:
        """Значение заголовка без учёта регистра."""
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None
