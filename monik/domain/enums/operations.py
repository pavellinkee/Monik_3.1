"""Типы операций и routing modes."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class OperationType(DomainEnum):
    """Направление обмена внутри арбитражного цикла (``10_LEVEL_1_SCANNER.md`` §8-10).

    ``BUY``  — input token -> intermediate token (например USDT -> AAVE).
    ``SELL`` — intermediate token -> output token (например AAVE -> USDT).
    """

    BUY = "buy"
    SELL = "sell"


class RouteValidationOutcome(DomainEnum):
    """Итог проверки зафиксированного маршрута Level 2.

    Соответствует ``06_AGGREGATOR_ADAPTERS.md`` §50-52: если API не умеет
    воспроизводить маршрут — ``UNSUPPORTED``; если вернул другой маршрут —
    ``MISMATCH``. Молча принимать альтернативный маршрут запрещено.
    """

    REPRODUCED = "reproduced"
    MISMATCH = "mismatch"
    UNSUPPORTED = "unsupported"


class RoutingMode(DomainEnum):
    """Normalized routing mode.

    Routing mode является частью identity маршрута (``06_AGGREGATOR_ADAPTERS.md`` §26):
    маршрут, полученный в разных режимах, не считается одним и тем же маршрутом.
    Фиктивные режимы создавать запрещено — если агрегатор не различает режимы,
    используется ``CLASSIC``.
    """

    CLASSIC = "classic"
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    UNISWAP_V4 = "uniswap_v4"
    UNISWAPX_DUTCH_V2 = "uniswapx_dutch_v2"
    UNISWAPX_DUTCH_V3 = "uniswapx_dutch_v3"
    UNISWAPX_PRIORITY = "uniswapx_priority"
