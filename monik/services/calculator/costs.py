"""Сведение компонентов стоимости в единую разбивку.

Каждый компонент сохраняется отдельно, чтобы результат можно было
восстановить (``09_PROFIT_CALCULATOR.md`` §33, §69).

Три правила, которые здесь реализованы буквально:

* неизвестный обязательный расход не превращается в ноль
  (``09_PROFIT_CALCULATOR.md`` §16, §63);
* расход, уже включённый в output amount quote, повторно не вычитается
  (``09_PROFIT_CALCULATOR.md`` §44-46);
* rebate хранится отдельным компонентом и не смешивается с комиссией
  (``09_PROFIT_CALCULATOR.md`` §15).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from monik.domain.enums.fees import CostInclusion, FeeType
from monik.domain.models.fee import Fee
from monik.domain.models.gas import Gas
from monik.domain.models.profit import CostBreakdown
from monik.domain.models.token import TokenKey
from monik.services.calculator.conversion import RateBook

__all__ = ["aggregate_costs"]

#: Типы, попадающие в ``other_costs`` (``09_PROFIT_CALCULATOR.md`` §62).
_OTHER_COST_TYPES = frozenset({FeeType.OTHER})

#: Типы, уменьшающие итоговую стоимость (``09_PROFIT_CALCULATOR.md`` §15).
_REBATE_TYPES = frozenset({FeeType.REBATE})


def _fee_label(index: int, fee: Fee) -> str:
    """Стабильная метка компонента для аудита неизвестных расходов."""
    return f"fee[{index}]:{fee.fee_type.value}"


def aggregate_costs(
    fees: tuple[Fee, ...],
    gas: Gas | None,
    *,
    currency: TokenKey,
    rates: RateBook,
    now: datetime,
) -> CostBreakdown:
    """Свести комиссии и gas к разбивке в валюте расчёта.

    Компонент, который невозможно достоверно оценить, попадает в
    ``unknown_components`` и не заменяется нулём. Такой расчёт не может
    быть ``COMPLETE``.
    """
    total_fees = Decimal(0)
    other_costs = Decimal(0)
    rebates = Decimal(0)
    unknown: list[str] = []

    for index, fee in enumerate(fees):
        label = _fee_label(index, fee)
        if not fee.is_known or not fee.is_fresh(now):
            # UNKNOWN / EXPIRED / UNSUPPORTED / ERROR: сумма отсутствует.
            unknown.append(label)
            continue
        if fee.inclusion is CostInclusion.INCLUDED_IN_QUOTE:
            # Комиссия уже отражена в output amount — второй раз не вычитаем.
            continue
        if fee.currency is None:  # pragma: no cover - защищено валидатором Fee
            unknown.append(f"{label}:currency")
            continue
        amount = rates.convert(fee.known_amount, from_token=fee.currency, to_token=currency)
        if amount is None:
            unknown.append(f"{label}:conversion")
            continue
        if fee.inclusion is CostInclusion.UNKNOWN:
            # Неизвестно, учтена ли комиссия в quote. Вычитаем (консервативно),
            # но расчёт полным не считается: двойной учёт исключить нельзя.
            unknown.append(f"{label}:inclusion")
        if fee.fee_type in _REBATE_TYPES:
            rebates += amount
        elif fee.fee_type in _OTHER_COST_TYPES:
            other_costs += amount
        else:
            total_fees += amount

    gas_cost, gas_unknown = _gas_cost(gas, currency=currency, rates=rates)
    unknown.extend(gas_unknown)

    return CostBreakdown(
        total_fees=total_fees,
        gas_cost=gas_cost,
        other_costs=other_costs,
        rebates=rebates,
        unknown_components=tuple(unknown),
    )


def _gas_cost(
    gas: Gas | None,
    *,
    currency: TokenKey,
    rates: RateBook,
) -> tuple[Decimal, list[str]]:
    """Стоимость газа в валюте расчёта и список неизвестных компонентов.

    Отсутствующий gas — это неизвестный расход, а не нулевой
    (``09_PROFIT_CALCULATOR.md`` §16): всякая on-chain операция расходует газ.
    """
    if gas is None:
        return Decimal(0), ["gas"]
    if gas.inclusion is CostInclusion.INCLUDED_IN_QUOTE:
        # Gas уже учтён в исходном financial value (§46).
        return Decimal(0), []
    if not gas.is_known or gas.native_token is None:
        return Decimal(0), ["gas"]

    amount = rates.convert(
        gas.known_cost_native,
        from_token=gas.native_token,
        to_token=currency,
    )
    if amount is None:
        return Decimal(0), ["gas:conversion"]
    unknown = ["gas:inclusion"] if gas.inclusion is CostInclusion.UNKNOWN else []
    return amount, unknown
