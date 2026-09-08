"""Единый формат сообщения об Opportunity.

Формат централизован (``15_NOTIFICATION_SYSTEM.md`` §47): разные части
приложения не создают собственных hard-coded форматов.

Formatter **ничего не пересчитывает** (§14, §50): он берёт значения из
готового снимка подтверждения и только форматирует их. Округление
выполняется исключительно для отображения и не влияет на исходный
финансовый результат (§49).

Level 2 ID показывается сверху, а к каждому уведомлению прикладывается
кнопка ``об`` (``CLAUDE.md`` §35).
"""

from __future__ import annotations

from decimal import Decimal

from monik.config.sections.notifications import NotificationConfig
from monik.domain.models.confirmation import AmountSnapshot, ConfirmationSnapshot
from monik.domain.models.token import TokenKey
from monik.services.registries.tokens import TokenRegistry

__all__ = ["DETAILS_BUTTON_LABEL", "MessageFormatter"]

#: Подпись кнопки, обязательной для каждого уведомления (``CLAUDE.md`` §35).
DETAILS_BUTTON_LABEL = "об"


class MessageFormatter:
    """Формирует текст уведомления и текст кнопки ``об`` из снимка."""

    def __init__(self, config: NotificationConfig, tokens: TokenRegistry) -> None:
        self._config = config
        self._tokens = tokens

    def render(self, snapshot: ConfirmationSnapshot) -> tuple[str, str]:
        """Вернуть основной текст и текст кнопки ``об``."""
        return (self.render_message(snapshot), self.render_details(snapshot))

    def render_message(self, snapshot: ConfirmationSnapshot) -> str:
        """Основное сообщение об Opportunity."""
        lines = [
            # Level 2 ID располагается сверху (``CLAUDE.md`` §35).
            f"{snapshot.k_id} ({snapshot.v_id})",
            f"Сеть: {snapshot.network_id}",
            f"Пара: {self._pair(snapshot)}",
            f"BUY: {snapshot.buy_provider_id.value}",
            f"SELL: {snapshot.sell_provider_id.value}",
            f"Подтверждено: {snapshot.confirmed_at.isoformat()}",
        ]
        for amount in snapshot.amounts:
            lines.extend(self._amount_lines(snapshot, amount))
        if self._config.show_calculation_version:
            lines.append(f"Версия расчёта: {snapshot.formula_version}")
        return "\n".join(lines)

    def render_details(self, snapshot: ConfirmationSnapshot) -> str:
        """Текст кнопки ``об``.

        Он формируется заранее и сохраняется вместе с уведомлением, поэтому
        нажатие кнопки не выполняет ни одного внешнего запроса
        (``CLAUDE.md`` §35).
        """
        lines = [
            f"{snapshot.k_id} — детали",
            f"Сеть: {snapshot.network_id}",
            f"Маршрут BUY: {self._route_line(snapshot, buy=True)}",
            f"Маршрут SELL: {self._route_line(snapshot, buy=False)}",
            f"Отпечаток BUY: {snapshot.routes.buy_route.fingerprint}",
            f"Отпечаток SELL: {snapshot.routes.sell_route.fingerprint}",
            f"Версия расчёта: {snapshot.formula_version}",
        ]
        for amount in snapshot.amounts:
            lines.extend(self._amount_details(snapshot, amount))
        return "\n".join(lines)

    # --- внутреннее -------------------------------------------------------

    def _pair(self, snapshot: ConfirmationSnapshot) -> str:
        """Тройка токенов цикла (``15_NOTIFICATION_SYSTEM.md`` §38)."""
        return (
            f"{self._symbol(snapshot.input_token)} → "
            f"{self._symbol(snapshot.intermediate_token)} → "
            f"{self._symbol(snapshot.output_token)}"
        )

    def _symbol(self, token: TokenKey) -> str:
        """Символ токена из реестра; идентичность остаётся канонической.

        Символ идентификатором не является (``36_DATA_MODELS.md`` §10):
        он используется только для отображения.
        """
        found = self._tokens.get(token)
        return found.symbol if found is not None else str(token)

    def _route_line(self, snapshot: ConfirmationSnapshot, *, buy: bool) -> str:
        route = snapshot.routes.buy_route if buy else snapshot.routes.sell_route
        steps = " → ".join(step.protocol for step in route.steps) or route.routing_mode.value
        return f"{route.provider_id.value} [{route.routing_mode.value}] {steps}"

    def _amount_lines(self, snapshot: ConfirmationSnapshot, amount: AmountSnapshot) -> list[str]:
        """Строки одной суммы (``15_NOTIFICATION_SYSTEM.md`` §39, §42-43)."""
        input_symbol = self._symbol(snapshot.input_token)
        header = f"{self._decimal(amount.input_amount.as_decimal)} {input_symbol}"
        if not amount.is_confirmed:
            return [f"{header}: не подтверждена ({amount.status.value})"]
        return [
            f"{header}: прибыль {self._optional(amount.net_profit)} {input_symbol}"
            f" · ROI {self._roi(amount)}"
        ]

    def _amount_details(self, snapshot: ConfirmationSnapshot, amount: AmountSnapshot) -> list[str]:
        """Разбивка одной суммы для кнопки ``об`` (§44-45)."""
        input_symbol = self._symbol(snapshot.input_token)
        lines = [
            f"— {self._decimal(amount.input_amount.as_decimal)} {input_symbol}"
            f" [{amount.status.value}]",
        ]
        if amount.buy_output is not None:
            lines.append(
                f"  BUY output: {self._decimal(amount.buy_output.as_decimal)} "
                f"{self._symbol(snapshot.intermediate_token)}"
            )
        if amount.sell_output is not None:
            lines.append(
                f"  SELL output: {self._decimal(amount.sell_output.as_decimal)} {input_symbol}"
            )
        costs = amount.costs
        if costs is not None:
            lines.extend(
                [
                    f"  Комиссии: {self._decimal(costs.total_fees)} {input_symbol}",
                    f"  Gas: {self._decimal(costs.gas_cost)} {input_symbol}",
                    f"  Прочие расходы: {self._decimal(costs.other_costs)} {input_symbol}",
                    f"  Rebate: {self._decimal(costs.rebates)} {input_symbol}",
                ]
            )
            if costs.unknown_components:
                lines.append(f"  Неизвестные компоненты: {', '.join(costs.unknown_components)}")
        gas = amount.gas
        if gas is not None:
            lines.append(f"  Gas статус: {gas.status.value}")
        lines.append(f"  Валовая прибыль: {self._optional(amount.gross_profit)} {input_symbol}")
        lines.append(f"  Чистая прибыль: {self._optional(amount.net_profit)} {input_symbol}")
        lines.append(f"  Чистый ROI: {self._roi(amount)}")
        if amount.threshold is not None:
            lines.append(f"  Порог: {self._decimal(amount.threshold)}%")
        if amount.rejection_reason:
            lines.append(f"  Причина: {amount.rejection_reason}")
        return lines

    def _roi(self, amount: AmountSnapshot) -> str:
        if amount.net_roi is None:
            return "n/a"
        return f"{self._decimal(amount.net_roi.value)}%"

    def _optional(self, value: Decimal | None) -> str:
        """Отсутствующее значение показывается как ``n/a``, а не как ноль."""
        return "n/a" if value is None else self._decimal(value)

    def _decimal(self, value: Decimal) -> str:
        """Округление только для отображения (``15_NOTIFICATION_SYSTEM.md`` §49-50)."""
        quantum = Decimal(1).scaleb(-self._config.decimal_places)
        return f"{value.quantize(quantum)}"
