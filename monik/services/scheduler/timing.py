"""Расчёт времени следующего запуска задачи.

Timezone задаётся явно (``14_SCHEDULER.md`` §9): неявное предположение о
UTC запрещено. Логика не строится на фиксированном offset, поэтому переход
на летнее/зимнее время обрабатывается корректно (§10).

Пропущенное расписание не превращается в очередь догоняющих запусков
(§34): выполняется максимум один catch-up.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from monik.domain.enums.scheduler import TaskMode
from monik.domain.models.scheduler import SchedulerTask

__all__ = ["local_run_instant", "next_run_at"]

#: Предел перебора дат при поиске следующего запуска.
_MAX_DAYS_AHEAD = 400


def local_run_instant(day: date, at_time: time, timezone_name: str) -> datetime:
    """Момент UTC, соответствующий локальному времени в заданный день.

    Переход на летнее время может сделать локальное время несуществующим
    (весенний скачок) или неоднозначным (осенний возврат).

    Несуществующее время сдвигается вперёд на величину перехода, поэтому
    запуск не теряется; неоднозначное выполняется один раз — по первому
    вхождению. Оба решения детерминированы и не опираются на фиксированный
    UTC offset (``14_SCHEDULER.md`` §10).
    """
    zone = ZoneInfo(timezone_name)
    naive = datetime.combine(day, at_time)
    first = naive.replace(tzinfo=zone, fold=0).astimezone(UTC)
    second = naive.replace(tzinfo=zone, fold=1).astimezone(UTC)
    if first == second:
        return first
    if first.astimezone(zone).replace(tzinfo=None) != naive:
        # Локального времени не существует: берём момент после перехода.
        return max(first, second)
    # Локальное время встречается дважды: берём первое вхождение.
    return min(first, second)


def next_run_at(
    task: SchedulerTask,
    *,
    now: datetime,
    last_run_at: datetime | None = None,
) -> datetime | None:
    """Когда задача должна выполниться в следующий раз.

    ``STARTUP`` и ``MANUAL`` собственного расписания не имеют
    (``14_SCHEDULER.md`` §13, §15), поэтому возвращается ``None``.
    """
    if not task.enabled:
        return None
    if task.mode is TaskMode.INTERVAL:
        return _next_interval_run(task, now=now, last_run_at=last_run_at)
    if task.mode is TaskMode.DAILY:
        return _next_daily_run(task, now=now, last_run_at=last_run_at)
    return None


def _next_interval_run(
    task: SchedulerTask, *, now: datetime, last_run_at: datetime | None
) -> datetime:
    """Следующий запуск интервальной задачи.

    Если пропущено несколько интервалов, планируется **один** запуск,
    а не серия догоняющих (``14_SCHEDULER.md`` §34, §53).
    """
    interval = task.interval
    if interval is None:  # pragma: no cover - защищено валидатором модели
        raise ValueError("INTERVAL task requires an interval")
    if last_run_at is None:
        return now
    scheduled = last_run_at + interval
    return scheduled if scheduled > now else now


def _next_daily_run(
    task: SchedulerTask, *, now: datetime, last_run_at: datetime | None
) -> datetime:
    """Следующий запуск ежедневной задачи с учётом ``interval_days``."""
    at_time = task.at_time
    timezone_name = task.timezone_name
    if at_time is None or timezone_name is None:  # pragma: no cover - валидатор модели
        raise ValueError("DAILY task requires at_time and timezone")

    zone = ZoneInfo(timezone_name)
    step = task.interval_days or 1
    if last_run_at is None:
        candidate = now.astimezone(zone).date()
    else:
        candidate = last_run_at.astimezone(zone).date() + timedelta(days=step)

    for _ in range(_MAX_DAYS_AHEAD):
        run_at = local_run_instant(candidate, at_time, timezone_name)
        if run_at > now:
            return run_at
        candidate += timedelta(days=1)
    raise ValueError(f"cannot determine next run for task {task.task_id}")
