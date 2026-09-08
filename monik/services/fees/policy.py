"""Fee Policy: нормализация правил комиссий конкретных провайдеров.

Provider-specific правила изолированы здесь и в адаптерах
(``06_AGGREGATOR_ADAPTERS.md`` §41): Scanner не содержит конструкций вида
``if aggregator == ...``. Изменение правил комиссии провайдера затрагивает
только его policy и тесты (``06_AGGREGATOR_ADAPTERS.md`` §42, §88).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from monik.domain.enums.fees import CostInclusion, FeeStatus, FeeType
from monik.domain.enums.providers import ProviderId
from monik.domain.models.fee import Fee
from monik.domain.value_objects.timestamps import UtcDatetime
from monik.services.fees.context import FeeContext

__all__ = [
    "FeePolicy",
    "PercentageFeePolicy",
    "QuoteInclusiveFeePolicy",
    "UnknownFeePolicy",
]


@runtime_checkable
class FeePolicy(Protocol):
    """Правила комиссий одного провайдера."""

    @property
    def provider_id(self) -> ProviderId:
        """Провайдер, к которому относится policy."""
        ...

    def components(self, context: FeeContext, *, observed_at: UtcDatetime) -> tuple[Fee, ...]:
        """Компоненты стоимости, применимые к операции."""
        ...


class QuoteInclusiveFeePolicy:
    """Комиссия агрегатора уже учтена в output котировки.

    Провайдер возвращает итоговую сумму маршрута, поэтому **дополнительно**
    вычитать нечего: соответствующий компонент имеет нулевую подлежащую
    вычитанию величину и признак ``INCLUDED_IN_QUOTE``. Это защищает от
    двойного учёта (``01_PROJECT_REQUIREMENTS.md`` §29,
    ``09_PROFIT_CALCULATOR.md`` §45).

    Ноль здесь означает «дополнительно вычитать нечего», а не «комиссии
    не существует»: сама комиссия отражена в котировке.
    """

    def __init__(self, provider_id: ProviderId, *, source: str) -> None:
        self._provider_id = provider_id
        self._source = source

    @property
    def provider_id(self) -> ProviderId:
        """Провайдер policy."""
        return self._provider_id

    def components(self, context: FeeContext, *, observed_at: UtcDatetime) -> tuple[Fee, ...]:
        """Единственный компонент: нечего вычитать дополнительно."""
        return (
            Fee(
                fee_type=FeeType.AGGREGATOR,
                status=FeeStatus.KNOWN,
                amount=Decimal(0),
                currency=context.output_token,
                inclusion=CostInclusion.INCLUDED_IN_QUOTE,
                source=self._source,
                observed_at=observed_at,
                description="aggregator fee is already reflected in the quoted output",
            ),
        )


class PercentageFeePolicy:
    """Процентная комиссия, вычитаемая дополнительно.

    База процента задаётся явно (``09_PROFIT_CALCULATOR.md`` §57):
    угадывать её запрещено. Здесь база — входная сумма операции.
    """

    def __init__(
        self,
        provider_id: ProviderId,
        *,
        rate_bps: int,
        fee_type: FeeType = FeeType.INTEGRATOR,
        source: str,
    ) -> None:
        if rate_bps < 0:
            raise ValueError("fee rate must not be negative")
        self._provider_id = provider_id
        self._rate_bps = rate_bps
        self._fee_type = fee_type
        self._source = source

    @property
    def provider_id(self) -> ProviderId:
        """Провайдер policy."""
        return self._provider_id

    def components(self, context: FeeContext, *, observed_at: UtcDatetime) -> tuple[Fee, ...]:
        """Компонент, рассчитанный от входной суммы."""
        amount = context.input_amount.as_decimal * Decimal(self._rate_bps) / Decimal(10_000)
        return (
            Fee(
                fee_type=self._fee_type,
                status=FeeStatus.KNOWN,
                amount=amount,
                currency=context.input_token,
                inclusion=CostInclusion.NOT_INCLUDED,
                source=self._source,
                observed_at=observed_at,
                description=f"{self._rate_bps} bps of the input amount",
            ),
        )


class UnknownFeePolicy:
    """Правила комиссии провайдера неизвестны.

    Возвращается компонент со статусом ``UNKNOWN`` **без суммы**: неизвестная
    комиссия никогда не считается нулевой (``07_FEE_SYSTEM.md`` §15,
    ``CLAUDE.md`` §23). Такой компонент не позволяет считать расчёт полным.
    """

    def __init__(
        self,
        provider_id: ProviderId,
        *,
        fee_type: FeeType = FeeType.AGGREGATOR,
        source: str,
        reason: str,
    ) -> None:
        self._provider_id = provider_id
        self._fee_type = fee_type
        self._source = source
        self._reason = reason

    @property
    def provider_id(self) -> ProviderId:
        """Провайдер policy."""
        return self._provider_id

    def components(self, context: FeeContext, *, observed_at: UtcDatetime) -> tuple[Fee, ...]:
        """Единственный компонент со статусом ``UNKNOWN``."""
        return (
            Fee(
                fee_type=self._fee_type,
                status=FeeStatus.UNKNOWN,
                inclusion=CostInclusion.UNKNOWN,
                source=self._source,
                observed_at=observed_at,
                description=self._reason,
            ),
        )
