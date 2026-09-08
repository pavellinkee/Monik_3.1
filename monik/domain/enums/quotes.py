"""Статусы normalized quote."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class QuoteStatus(DomainEnum):
    """Валидность quote (``21_API_CONTRACTS.md`` §11-14).

    ``STALE`` и ``EXPIRED`` различаются намеренно: stale quote ещё может
    использоваться для diagnostics, но не для confirmation.
    """

    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"
    EXPIRED = "expired"
