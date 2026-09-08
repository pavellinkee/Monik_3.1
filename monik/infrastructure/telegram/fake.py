"""Детерминированный транспорт Telegram для тестов.

**Test implementation, не production** (``CLAUDE.md`` §10, §46): позволяет
проверять очередь, retry и восстановление без обращения к Bot API.
"""

from __future__ import annotations

from collections.abc import Callable

from monik.services.notifications.ports import DeliveryReceipt, OutgoingMessage

__all__ = ["FakeTransport"]

#: Правило, определяющее результат конкретной попытки.
ReceiptRule = Callable[[int, OutgoingMessage], DeliveryReceipt]


class FakeTransport:
    """Транспорт с предсказуемым результатом доставки."""

    def __init__(
        self,
        *,
        receipt: DeliveryReceipt | None = None,
        rule: ReceiptRule | None = None,
    ) -> None:
        self._receipt = receipt or DeliveryReceipt(delivered=True, external_message_id="1")
        self._rule = rule
        self.sent: list[OutgoingMessage] = []

    async def send(self, message: OutgoingMessage) -> DeliveryReceipt:
        """Записать сообщение и вернуть заданный результат."""
        self.sent.append(message)
        if self._rule is not None:
            return self._rule(len(self.sent), message)
        return self._receipt
