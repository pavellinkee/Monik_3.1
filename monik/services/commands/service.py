"""Входящий канал команд.

Telegram не блокирует Scanner (``CLAUDE.md`` §35): обработка команд
выполняется отдельной задачей и не участвует в цикле сканирования.

Обработчики читают только сохранённые данные, поэтому команда не может
инициировать запрос к провайдеру котировок.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from monik.domain.errors import MonikError
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.telegram.polling import TelegramUpdate
from monik.services.commands.handlers import CommandResponse, CommandRouter
from monik.services.notifications.ports import NotificationTransport, OutgoingMessage
from monik.services.observability.clock import Clock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["CommandService", "OffsetStore", "UpdateSource"]

_LOGGER = get_logger("services.commands.service")

#: Ключ, под которым хранится offset входящих обновлений.
OFFSET_KEY = "telegram.updates.offset"


@runtime_checkable
class UpdateSource(Protocol):
    """Источник входящих обновлений."""

    async def fetch(self, *, offset: int | None, limit: int = 20) -> tuple[TelegramUpdate, ...]:
        """Получить порцию обновлений."""
        ...

    async def answer_callback(self, callback_query_id: str, *, text: str | None = None) -> None:
        """Подтвердить обработку нажатия кнопки."""
        ...


@runtime_checkable
class OffsetStore(Protocol):
    """Хранилище offset, переживающее рестарт."""

    async def get(self, key: str) -> str | None:
        """Значение по ключу."""
        ...

    async def set(self, key: str, value: str, *, updated_at: datetime) -> None:
        """Записать значение."""
        ...


@dataclass
class CommandService:
    """Читает обновления, маршрутизирует команды и отправляет ответы."""

    router: CommandRouter
    updates: UpdateSource
    transport: NotificationTransport
    destination: NotificationDestination
    offsets: OffsetStore
    clock: Clock
    allowed_chat_ids: frozenset[str] = frozenset()
    batch_size: int = 20
    handled_update_ids: set[int] = field(default_factory=set)

    async def poll_once(self) -> tuple[CommandResponse, ...]:
        """Обработать одну порцию обновлений.

        Ошибка обработки одной команды не останавливает канал: она
        фиксируется и обработка продолжается.
        """
        offset = await self._load_offset()
        try:
            batch = await self.updates.fetch(offset=offset, limit=self.batch_size)
        except MonikError as error:
            _LOGGER.warning(
                "telegram updates unavailable",
                extra=log_fields(error_category=error.info.category.value),
            )
            return ()

        responses = []
        highest = offset - 1 if offset is not None else None
        for update in batch:
            highest = update.update_id if highest is None else max(highest, update.update_id)
            response = await self._handle(update)
            if response is not None:
                responses.append(response)
        if highest is not None:
            await self._store_offset(highest + 1)
        return tuple(responses)

    # --- внутреннее -------------------------------------------------------

    async def _handle(self, update: TelegramUpdate) -> CommandResponse | None:
        if update.update_id in self.handled_update_ids:
            # Telegram доставляет обновления как минимум один раз.
            return None
        self.handled_update_ids.add(update.update_id)

        if not self._is_allowed(update):
            _LOGGER.warning(
                "command from an unknown chat ignored",
                extra=log_fields(update_id=update.update_id),
            )
            return None

        try:
            if update.is_callback and update.callback_data is not None:
                response = await self.router.handle_callback(update.callback_data)
                if update.callback_query_id is not None:
                    await self.updates.answer_callback(update.callback_query_id)
            elif update.is_command and update.text is not None:
                response = await self.router.handle_text(update.text)
            else:
                return None
        except MonikError as error:
            _LOGGER.warning(
                "command handling failed",
                extra=log_fields(
                    update_id=update.update_id,
                    error_category=error.info.category.value,
                ),
            )
            return None

        await self._reply(response)
        return response

    def _is_allowed(self, update: TelegramUpdate) -> bool:
        """Источник команды обязан быть разрешён конфигурацией.

        Destination является configuration identity и не может приходить
        произвольным внешним вводом (``36_DATA_MODELS.md`` §83).
        """
        if not self.allowed_chat_ids:
            return True
        return update.chat_id is not None and update.chat_id in self.allowed_chat_ids

    async def _reply(self, response: CommandResponse) -> None:
        try:
            await self.transport.send(
                OutgoingMessage(destination=self.destination, text=response.text)
            )
        except MonikError as error:
            _LOGGER.warning(
                "command reply failed",
                extra=log_fields(error_category=error.info.category.value),
            )

    async def _load_offset(self) -> int | None:
        stored = await self.offsets.get(OFFSET_KEY)
        if stored is None:
            return None
        try:
            return int(stored)
        except ValueError:
            _LOGGER.warning("stored telegram offset is not a number")
            return None

    async def _store_offset(self, offset: int) -> None:
        await self.offsets.set(OFFSET_KEY, str(offset), updated_at=self.clock.now())
