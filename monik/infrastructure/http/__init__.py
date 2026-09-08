"""Controlled async HTTP client (timeouts, TLS, SSRF, limits).

Business logic не импортирует HTTP-библиотеки напрямую
(``25_PROJECT_STRUCTURE.md`` §62); все внешние запросы проходят через
Resource Manager и Adapter'ы.
"""

from monik.infrastructure.http.client import HttpClient, HttpxClient, classify_response
from monik.infrastructure.http.fake import FakeHttpClient
from monik.infrastructure.http.models import HttpRequest, HttpResponse
from monik.infrastructure.http.safety import UrlPolicy

__all__ = [
    "FakeHttpClient",
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "HttpxClient",
    "UrlPolicy",
    "classify_response",
]
