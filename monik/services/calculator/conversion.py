"""Перевод сумм в валюту расчёта внутри одного calculation context.

Calculator не выполняет внешних запросов (``09_PROFIT_CALCULATOR.md`` §74):
все курсы приходят во входной модели. Здесь они только выбираются и
применяются.

Направление конверсии учитывается явно (``09_PROFIT_CALCULATOR.md`` §38):
курс ``ETH -> USDT`` не используется как ``USDT -> ETH``. Обратный
пересчёт — отдельное решение вызывающей подсистемы, а не молчаливая
подстановка внутри расчёта.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from monik.domain.models.conversion import ConversionRate
from monik.domain.models.token import TokenKey

__all__ = ["RateBook"]


class RateBook:
    """Курсы, доступные конкретному расчёту.

    Устаревший курс не применяется (``09_PROFIT_CALCULATOR.md`` §36):
    отсутствие свежего курса делает соответствующий компонент неизвестным,
    а не нулевым.
    """

    def __init__(self, rates: tuple[ConversionRate, ...], *, now: datetime) -> None:
        self._now = now
        self._rates: dict[tuple[str, str], ConversionRate] = {}
        for rate in rates:
            if not rate.is_fresh(now):
                continue
            key = (str(rate.from_token), str(rate.to_token))
            # Первый свежий курс пары выигрывает: порядок входных данных
            # задаётся вызывающей подсистемой и детерминирован.
            self._rates.setdefault(key, rate)

    def rate_for(self, from_token: TokenKey, to_token: TokenKey) -> ConversionRate | None:
        """Свежий курс заданного направления, если он предоставлен."""
        return self._rates.get((str(from_token), str(to_token)))

    def convert(
        self,
        amount: Decimal,
        *,
        from_token: TokenKey,
        to_token: TokenKey,
    ) -> Decimal | None:
        """Перевести сумму в ``to_token``.

        Совпадающие валюты не требуют конверсии
        (``09_PROFIT_CALCULATOR.md`` §34). Отсутствие подходящего свежего
        курса возвращает ``None`` — придумывать значение запрещено
        (``09_PROFIT_CALCULATOR.md`` §37).
        """
        if from_token == to_token:
            return amount
        rate = self.rate_for(from_token, to_token)
        if rate is None:
            return None
        return rate.convert(amount)
