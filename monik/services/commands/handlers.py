"""Обработчики команд Telegram.

Ответ формируется **только** из сохранённых данных (``CLAUDE.md`` §35):
обработчик не обращается к провайдерам котировок, не выполняет расчётов и
не запускает сканирование.

Некорректный ввод превращается в понятный ответ, а не в ошибку подсистемы.
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.domain.enums.lifecycle import JobStatus
from monik.domain.errors import DomainValidationError
from monik.domain.models.job import ConfirmationResult, Level2Job
from monik.domain.value_objects.identifiers import KId
from monik.services.commands.parser import (
    CommandName,
    ParsedCommand,
    parse_callback,
    parse_command,
)
from monik.services.commands.ports import (
    JobReader,
    NotificationReader,
    StatsSource,
    StatusSource,
)
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["CommandResponse", "CommandRouter"]

_LOGGER = get_logger("services.commands")

#: Сколько активных Job показывать в ``/level2``.
_ACTIVE_JOB_LIMIT = 20

#: Статусы, считающиеся активными для ``/level2``.
_ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


@dataclass(frozen=True, slots=True)
class CommandResponse:
    """Текст ответа и признак успешной обработки."""

    text: str
    handled: bool = True


class CommandRouter:
    """Маршрутизирует команды и нажатия кнопки ``об``."""

    def __init__(
        self,
        *,
        jobs: JobReader,
        notifications: NotificationReader,
        status: StatusSource,
        stats: StatsSource,
    ) -> None:
        self._jobs = jobs
        self._notifications = notifications
        self._status = status
        self._stats = stats

    async def handle_text(self, text: str) -> CommandResponse:
        """Обработать текстовую команду."""
        command = parse_command(text)
        if command.error is not None:
            return CommandResponse(text=command.error, handled=False)
        return await self._dispatch(command)

    async def handle_callback(self, data: str) -> CommandResponse:
        """Обработать нажатие кнопки ``об``.

        Текст берётся из сохранённого уведомления: новых внешних запросов
        не выполняется (``CLAUDE.md`` §35).
        """
        notification_id = parse_callback(data)
        if notification_id is None:
            return CommandResponse(text="неизвестное действие", handled=False)
        _, details = await self._notifications.load_texts(notification_id)
        if details is None:
            return CommandResponse(text="детали недоступны", handled=False)
        return CommandResponse(text=details)

    # --- обработчики ------------------------------------------------------

    async def _dispatch(self, command: ParsedCommand) -> CommandResponse:
        if command.name is CommandName.DETAILS:
            return await self._details(command.argument or "")
        if command.name is CommandName.LEVEL2:
            return await self._level2()
        if command.name is CommandName.STATUS:
            return self._status_response()
        if command.name is CommandName.STATS:
            return self._stats_response()
        return CommandResponse(text="неизвестная команда", handled=False)

    async def _details(self, raw_k_id: str) -> CommandResponse:
        """``/details K1234`` — сохранённый результат проверки."""
        try:
            k_id = KId(raw_k_id)
        except (ValueError, DomainValidationError):
            return CommandResponse(text=f"некорректный идентификатор: {raw_k_id}", handled=False)

        job = await self._jobs.get(k_id)
        if job is None:
            return CommandResponse(text=f"{k_id} не найден", handled=False)
        result = await self._jobs.load_confirmation(k_id, job.attempt_count)
        if result is None:
            return CommandResponse(
                text=f"{k_id}: статус {job.status.value}, результат проверки ещё не сохранён"
            )
        return CommandResponse(text=_details_text(result, job.status))

    async def _level2(self) -> CommandResponse:
        """``/level2`` — активные Job'ы."""
        active: list[Level2Job] = []
        for status in _ACTIVE_STATUSES:
            active.extend(await self._jobs.list_by_status(status, limit=_ACTIVE_JOB_LIMIT))
        if not active:
            return CommandResponse(text="активных Level 2 задач нет")
        lines = ["Активные Level 2 задачи:"]
        lines.extend(
            f"{job.k_id} · {job.status.value} · попыток {job.attempt_count}"
            for job in sorted(active, key=lambda item: item.created_at)
        )
        return CommandResponse(text="\n".join(lines))

    def _status_response(self) -> CommandResponse:
        """``/status`` — состояние подсистем."""
        components = self._status.components()
        if not components:
            return CommandResponse(text="состояние подсистем недоступно", handled=False)
        lines = ["Состояние подсистем:"]
        lines.extend(
            f"{item.name}: {item.state}" + (f" ({item.detail})" if item.detail else "")
            for item in components
        )
        return CommandResponse(text="\n".join(lines))

    def _stats_response(self) -> CommandResponse:
        """``/stats`` — накопленная статистика."""
        snapshot = self._stats.snapshot()
        rate = snapshot.confirmations.confirmation_rate
        _LOGGER.info("stats requested", extra=log_fields(decided=snapshot.confirmations.decided))
        lines = [
            "Статистика:",
            f"Циклов Level 1: {snapshot.scans_completed}",
            f"Возможностей создано: {snapshot.opportunities_created}",
            f"Уведомлений отправлено: {snapshot.notifications_sent}",
            f"Подтверждено сумм: {snapshot.confirmations.confirmed}",
            f"Не подтверждено сумм: {snapshot.confirmations.unconfirmed}",
            f"Неопределённых сумм: {snapshot.confirmations.partial}",
            # PARTIAL исключается из расчёта; отсутствие решений даёт N/A
            # (``CLAUDE.md`` §27).
            f"Confirmation rate: {'N/A' if rate is None else f'{rate:.2f}%'}",
        ]
        return CommandResponse(text="\n".join(lines))


def _details_text(result: ConfirmationResult, job_status: JobStatus) -> str:
    """Текст ответа ``/details`` из сохранённого результата."""
    lines = [
        f"{result.k_id} · {job_status.value} · проверка #{result.revision}",
        f"Итог: {result.job_status.value}",
        f"Подтверждено: {result.confirmed_count} · "
        f"не подтверждено: {result.unconfirmed_count} · "
        f"неопределённых: {result.partial_count}",
    ]
    for amount in result.amount_results:
        line = f"— {amount.input_amount.as_decimal}: {amount.status.value}"
        if amount.rejection_reason:
            line += f" ({amount.rejection_reason})"
        lines.append(line)
    if result.failure_reason:
        lines.append(f"Причина: {result.failure_reason}")
    return "\n".join(lines)
