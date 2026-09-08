"""Opportunity — сущность, создаваемая Level 1, и её промежуточный Candidate.

Решение D-1 (``DEVELOPMENT_PLAN.md`` §9): ``Opportunity`` — официальное имя
результата Level 1; ``Candidate`` — промежуточный результат до прохождения
необходимых проверок, который не персистится.

Ключевое архитектурное правило: **все суммы одной Opportunity используют
один и тот же маршрут**, зафиксированный Level 1
(``10_LEVEL_1_SCANNER.md`` §24, §89), но каждая сумма получает собственный
финансовый результат (``10_LEVEL_1_SCANNER.md`` §90).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Self

from pydantic import Field, model_validator

from monik.domain.enums.lifecycle import OpportunityStatus
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.base import DomainModel
from monik.domain.models.profit import ProfitResult
from monik.domain.models.quote import Quote
from monik.domain.models.route import Route
from monik.domain.models.token import TokenKey
from monik.domain.value_objects.amounts import TokenAmount
from monik.domain.value_objects.fingerprints import OpportunityFingerprint, compute_fingerprint
from monik.domain.value_objects.identifiers import OpportunityId, ScanId, VId
from monik.domain.value_objects.identity import NetworkId
from monik.domain.value_objects.timestamps import UtcDatetime

__all__ = [
    "Candidate",
    "Opportunity",
    "OpportunityAmount",
    "RouteSnapshot",
    "opportunity_fingerprint",
]


def opportunity_fingerprint(
    *,
    routes: RouteSnapshot,
    buy_provider_id: ProviderId,
    sell_provider_id: ProviderId,
) -> OpportunityFingerprint:
    """Детерминированный отпечаток логической возможности.

    Учитывает сеть, тройку токенов, пару агрегаторов и отпечатки обоих
    маршрутов (``10_LEVEL_1_SCANNER.md`` §53). Не зависит от случайного
    идентификатора (``04_SCHEDULER.md`` §23), поэтому пригоден для
    дедупликации ещё до создания самой Opportunity.
    """
    payload: dict[str, Any] = {
        "network_id": str(routes.network_id),
        "input_token": str(routes.input_token),
        "intermediate_token": str(routes.intermediate_token),
        "output_token": str(routes.output_token),
        "buy_provider_id": buy_provider_id.value,
        "sell_provider_id": sell_provider_id.value,
        "buy_route_fingerprint": str(routes.buy_route.fingerprint),
        "sell_route_fingerprint": str(routes.sell_route.fingerprint),
    }
    return OpportunityFingerprint(compute_fingerprint(payload))


class RouteSnapshot(DomainModel):
    """Зафиксированная Level 1 пара маршрутов BUY и SELL.

    Level 2 обязан проверять именно эти маршруты и не имеет права выбрать
    другие (``11_LEVEL_2_SCANNER.md`` §5, ``10_LEVEL_1_SCANNER.md`` §31).
    """

    buy_route: Route
    sell_route: Route

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Маршруты обязаны образовывать связный round-trip в одной сети."""
        if self.buy_route.operation is not OperationType.BUY:
            raise ValueError("buy_route must describe a BUY operation")
        if self.sell_route.operation is not OperationType.SELL:
            raise ValueError("sell_route must describe a SELL operation")
        if self.buy_route.network_id != self.sell_route.network_id:
            raise ValueError("buy and sell routes must belong to the same network")
        if self.buy_route.output_token != self.sell_route.input_token:
            raise ValueError(
                "sell route must start from the intermediate token produced by the buy route"
            )
        if self.buy_route.input_token != self.sell_route.output_token:
            raise ValueError("round-trip opportunity must end at the input token")
        return self

    @property
    def network_id(self) -> NetworkId:
        """Сеть, к которой относятся оба маршрута."""
        return self.buy_route.network_id

    @property
    def input_token(self) -> TokenKey:
        """Входной токен цикла."""
        return self.buy_route.input_token

    @property
    def intermediate_token(self) -> TokenKey:
        """Промежуточный токен цикла."""
        return self.buy_route.output_token

    @property
    def output_token(self) -> TokenKey:
        """Выходной токен цикла (для round-trip совпадает со входным)."""
        return self.sell_route.output_token


class OpportunityAmount(DomainModel):
    """Контекст одной суммы внутри Opportunity.

    Каждая сумма рассчитывается независимо: результат одной суммы нельзя
    переносить на другую (``09_PROFIT_CALCULATOR.md`` §54,
    ``02_LEVEL1_SCANNER.md`` §20).
    """

    input_amount: TokenAmount
    preliminary_result: ProfitResult
    preliminary_buy_output: TokenAmount
    preliminary_sell_output: TokenAmount

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.input_amount.raw <= 0:
            raise ValueError("opportunity amount must be positive")
        if self.preliminary_result.input_amount != self.input_amount:
            raise ValueError("preliminary result does not describe this amount")
        return self


class Candidate(DomainModel):
    """Промежуточный результат Level 1 до прохождения проверок (решение D-1).

    Candidate связывает конкретные BUY и SELL quotes для одной суммы и
    предварительный расчёт. Он живёт только внутри цикла Level 1: в БД
    не сохраняется, Level 2 его не получает.
    """

    scan_id: ScanId
    buy_quote: Quote
    sell_quote: Quote
    preliminary_result: ProfitResult
    detected_at: UtcDatetime

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Quotes обязаны образовывать согласованный round-trip.

        BUY output token обязан совпадать с SELL input token
        (``10_LEVEL_1_SCANNER.md`` §82), а финальный токен — с исходным
        (``10_LEVEL_1_SCANNER.md`` §83).
        """
        if self.buy_quote.operation is not OperationType.BUY:
            raise ValueError("buy_quote must be a BUY quote")
        if self.sell_quote.operation is not OperationType.SELL:
            raise ValueError("sell_quote must be a SELL quote")
        if self.buy_quote.network_id != self.sell_quote.network_id:
            raise ValueError("candidate quotes must belong to the same network")
        if self.buy_quote.output_token != self.sell_quote.input_token:
            raise ValueError("sell quote must start from the buy quote intermediate token")
        if self.buy_quote.input_token != self.sell_quote.output_token:
            raise ValueError("round-trip candidate must end at the input token")
        if self.sell_quote.input_amount != self.buy_quote.output_amount:
            raise ValueError("sell quote input amount must equal the buy quote output amount")
        return self

    @property
    def route_snapshot(self) -> RouteSnapshot:
        """Маршруты, зафиксированные этим кандидатом."""
        return RouteSnapshot(buy_route=self.buy_quote.route, sell_route=self.sell_quote.route)

    def to_amount_context(self) -> OpportunityAmount:
        """Преобразовать кандидата в amount-контекст Opportunity."""
        return OpportunityAmount(
            input_amount=self.buy_quote.input_amount,
            preliminary_result=self.preliminary_result,
            preliminary_buy_output=self.buy_quote.output_amount,
            preliminary_sell_output=self.sell_quote.output_amount,
        )


class Opportunity(DomainModel):
    """Возможность, обнаруженная Level 1 (решение D-1).

    Level 1 фиксирует маршрут; Level 2 проверяет именно его
    (``10_LEVEL_1_SCANNER.md`` §95). До подтверждения Level 2 Opportunity
    не является подтверждённой возможностью (``10_LEVEL_1_SCANNER.md`` §3).

    После перехода в ``CONFIRMED``/``PARTIAL`` финансовый снимок неизменяем
    обычным workflow (``36_DATA_MODELS.md`` §45, ``35_STATE_MACHINES.md`` §66).
    """

    opportunity_id: OpportunityId
    v_id: VId
    scan_id: ScanId
    status: OpportunityStatus
    buy_provider_id: ProviderId
    sell_provider_id: ProviderId
    routes: RouteSnapshot
    amounts: tuple[OpportunityAmount, ...] = Field(min_length=1)
    detected_at: UtcDatetime
    expires_at: UtcDatetime
    updated_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        """Провайдеры маршрутов и суммы обязаны быть согласованы."""
        if self.routes.buy_route.provider_id != self.buy_provider_id:
            raise ValueError("buy route provider does not match buy_provider_id")
        if self.routes.sell_route.provider_id != self.sell_provider_id:
            raise ValueError("sell route provider does not match sell_provider_id")
        if self.expires_at <= self.detected_at:
            raise ValueError("opportunity expires_at must be after detected_at")
        seen: set[int] = set()
        for amount in self.amounts:
            if amount.input_amount.raw in seen:
                raise ValueError("opportunity contains duplicate input amounts")
            seen.add(amount.input_amount.raw)
        return self

    @property
    def network_id(self) -> NetworkId:
        """Сеть возможности."""
        return self.routes.network_id

    @property
    def input_token(self) -> TokenKey:
        """Входной токен."""
        return self.routes.input_token

    @property
    def intermediate_token(self) -> TokenKey:
        """Промежуточный токен."""
        return self.routes.intermediate_token

    @property
    def output_token(self) -> TokenKey:
        """Выходной токен."""
        return self.routes.output_token

    @property
    def fingerprint(self) -> OpportunityFingerprint:
        """Детерминированный отпечаток логической возможности.

        Вычисляется той же функцией, что использует Level 1 до создания
        Opportunity, поэтому дедупликация и хранимое значение совпадают.
        """
        return opportunity_fingerprint(
            routes=self.routes,
            buy_provider_id=self.buy_provider_id,
            sell_provider_id=self.sell_provider_id,
        )

    def is_expired(self, now: UtcDatetime) -> bool:
        """Истёк ли срок, в течение которого возможность можно проверять."""
        return now >= self.expires_at

    def time_to_expiry(self, now: UtcDatetime) -> timedelta:
        """Сколько времени осталось до истечения срока."""
        return self.expires_at - now

    def amount_for(self, raw_input_amount: int) -> OpportunityAmount:
        """Найти amount-контекст по raw входной сумме."""
        for amount in self.amounts:
            if amount.input_amount.raw == raw_input_amount:
                return amount
        raise KeyError(f"opportunity {self.v_id} has no amount context for {raw_input_amount}")
