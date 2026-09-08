"""Независимый цикл одного промежуточного токена.

Ключевое требование: **BUY одного токена, завершившийся полностью, немедленно
запускает свой SELL и не ждёт BUY других токенов** (``CLAUDE.md`` §16,
``10_LEVEL_1_SCANNER.md`` §75). Поэтому цикл токена самодостаточен и
запускается параллельно с циклами остальных токенов.

MAX BUY определяется только после получения необходимого набора BUY-ответов
(``10_LEVEL_1_SCANNER.md`` §12): SELL считается от фактического выхода
лучшего BUY.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.opportunity import Candidate
from monik.domain.models.quote import Quote
from monik.domain.models.token import Token
from monik.domain.value_objects.identifiers import ScanId
from monik.domain.value_objects.identity import NetworkId
from monik.infrastructure.providers.contract import AggregatorAdapter
from monik.services.level1.filters import CombinationFilter
from monik.services.level1.preliminary import PreliminaryEvaluator
from monik.services.level1.quotes import QuoteAttempt, QuoteCollector
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["TokenCycle"]

_LOGGER = get_logger("services.level1.cycle")


@dataclass(frozen=True, slots=True)
class _Leg:
    """Пара «провайдер — котировка», прошедшая валидацию."""

    provider_id: ProviderId
    quote: Quote


class TokenCycle:
    """Полный цикл ``base → token → base`` для всех сумм одного токена."""

    def __init__(
        self,
        *,
        collector: QuoteCollector,
        combinations: CombinationFilter,
        evaluator: PreliminaryEvaluator,
        adapters: dict[ProviderId, AggregatorAdapter],
        clock: Clock,
        scan_id: ScanId,
        network_id: NetworkId,
        base_token: Token,
        providers: tuple[ProviderId, ...],
        pairs: tuple[tuple[ProviderId, ProviderId], ...],
        raw_amounts: tuple[int, ...],
    ) -> None:
        self._collector = collector
        self._combinations = combinations
        self._evaluator = evaluator
        self._adapters = adapters
        self._clock = clock
        self._scan_id = scan_id
        self._network_id = network_id
        self._base_token = base_token
        self._providers = providers
        self._pairs = pairs
        self._raw_amounts = raw_amounts

    async def run(self, token: Token) -> tuple[Candidate, ...]:
        """Проверить все суммы для промежуточного токена.

        Каждая сумма — самостоятельный контекст: результат одной суммы не
        переносится на другую (``02_LEVEL1_SCANNER.md`` §20).
        """
        results = await asyncio.gather(
            *(self._run_amount(token, raw_amount) for raw_amount in self._raw_amounts)
        )
        return tuple(candidate for group in results for candidate in group)

    async def _run_amount(self, token: Token, raw_amount: int) -> tuple[Candidate, ...]:
        best_buy = await self._max_buy(token, raw_amount)
        if best_buy is None:
            return ()
        sell_legs = await self._sell_legs(token, best_buy)
        candidates = []
        for leg in sell_legs:
            candidate = await self._build_candidate(best_buy.quote, leg.quote)
            if candidate is not None:
                candidates.append(candidate)
        return tuple(candidates)

    async def _max_buy(self, token: Token, raw_amount: int) -> _Leg | None:
        """Лучший BUY среди провайдеров, допущенных фильтром."""
        buy_providers = tuple(
            provider_id
            for provider_id in self._providers
            if any(pair[0] is provider_id for pair in self._pairs)
        )
        attempts = await self._gather_quotes(
            buy_providers,
            operation=OperationType.BUY,
            input_token=self._base_token,
            output_token=token,
            raw_amount=raw_amount,
            amount_token=self._base_token,
        )
        legs = _usable_legs(attempts)
        if not legs:
            return None
        # Детерминированный выбор: наибольший output, при равенстве —
        # стабильный порядок по идентификатору провайдера.
        return max(legs, key=lambda leg: (leg.quote.output_amount.raw, leg.provider_id.value))

    async def _sell_legs(self, token: Token, best_buy: _Leg) -> tuple[_Leg, ...]:
        """SELL-котировки, разрешённые для найденного BUY-провайдера."""
        sell_providers = tuple(
            provider_id
            for provider_id in self._providers
            if (best_buy.provider_id, provider_id) in set(self._pairs)
        )
        attempts = await self._gather_quotes(
            sell_providers,
            operation=OperationType.SELL,
            input_token=token,
            output_token=self._base_token,
            raw_amount=best_buy.quote.output_amount.raw,
            amount_token=token,
        )
        return _usable_legs(attempts)

    async def _gather_quotes(
        self,
        providers: tuple[ProviderId, ...],
        *,
        operation: OperationType,
        input_token: Token,
        output_token: Token,
        raw_amount: int,
        amount_token: Token,
    ) -> tuple[QuoteAttempt, ...]:
        allowed = []
        for provider_id in providers:
            adapter = self._adapters.get(provider_id)
            if adapter is None:
                continue
            if not self._combinations.allows(
                adapter,
                network_id=self._network_id,
                operation=operation,
                token=output_token if operation is OperationType.BUY else input_token,
            ):
                self._collector.record_skipped()
                continue
            allowed.append(provider_id)
        if not allowed:
            return ()
        amount = amount_token.amount_from_base_units(raw_amount)
        return tuple(
            await asyncio.gather(
                *(
                    self._collector.fetch(
                        provider_id,
                        network_id=self._network_id,
                        operation=operation,
                        input_token=input_token,
                        output_token=output_token,
                        input_amount=amount,
                    )
                    for provider_id in allowed
                )
            )
        )

    async def _build_candidate(self, buy_quote: Quote, sell_quote: Quote) -> Candidate | None:
        """Собрать кандидата и его предварительный результат."""
        try:
            preliminary = await self._evaluator.evaluate(buy_quote, sell_quote)
            return Candidate(
                scan_id=self._scan_id,
                buy_quote=buy_quote,
                sell_quote=sell_quote,
                preliminary_result=preliminary,
                detected_at=self._clock.now(),
            )
        except ValueError as error:
            # Несогласованная пара котировок кандидатом не становится
            # (``10_LEVEL_1_SCANNER.md`` §81).
            _LOGGER.info("candidate rejected", extra=log_fields(reason=str(error)))
            return None


def _usable_legs(attempts: tuple[QuoteAttempt, ...]) -> tuple[_Leg, ...]:
    """Оставить только валидные котировки."""
    return tuple(
        _Leg(provider_id=attempt.provider_id, quote=attempt.quote)
        for attempt in attempts
        if attempt.is_usable and attempt.quote is not None
    )
