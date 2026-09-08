"""Валидация котировки до участия в сравнении прибыльности.

Невалидная котировка не участвует в сравнении
(``10_LEVEL_1_SCANNER.md`` §41, ``02_LEVEL1_SCANNER.md`` §24), а причина
фиксируется в диагностике. Нулевой output валидной возможностью не является
(``02_LEVEL1_SCANNER.md`` §25).
"""

from __future__ import annotations

from datetime import timedelta

from monik.domain.enums.providers import ProviderId
from monik.domain.enums.quotes import QuoteStatus
from monik.domain.models.quote import Quote
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.infrastructure.providers.contract import QuoteRequest

__all__ = ["quote_rejection_reason"]


def quote_rejection_reason(
    quote: Quote,
    request: QuoteRequest,
    *,
    provider_id: ProviderId,
    now: UtcDatetime,
    max_age: timedelta,
) -> str | None:
    """Причина, по которой котировку нельзя использовать, либо ``None``.

    Проверяются провайдер, сеть, токены, сумма, статус и свежесть
    (``02_LEVEL1_SCANNER.md`` §23, ``10_LEVEL_1_SCANNER.md`` §40).
    """
    if quote.provider_id is not provider_id:
        return "quote was returned by a different provider"
    if quote.network_id != request.network_id:
        return "quote belongs to a different network"
    if quote.operation is not request.operation:
        return "quote describes a different operation"
    if quote.input_token != request.input_token.key:
        return "quote input token does not match the request"
    if quote.output_token != request.output_token.key:
        return "quote output token does not match the request"
    if quote.input_amount != request.input_amount:
        return "quote input amount does not match the request"
    if quote.status is not QuoteStatus.VALID:
        return f"quote status is {quote.status.value}"
    if not quote.has_usable_output:
        return "quote output amount is zero"
    if quote.output_amount.decimals != request.output_token.decimals:
        return "quote output decimals do not match the output token"
    if not quote.is_fresh(now, max_age):
        return "quote is not fresh enough for this scan"
    return None
