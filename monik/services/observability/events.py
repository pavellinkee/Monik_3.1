"""События переходов состояний.

Каждый критический переход наблюдаем (``35_STATE_MACHINES.md`` §118):
сущность, предыдущее и новое состояние, момент, машиночитаемая причина и
correlation id. Событие фиксируется как факт и не изменяет саму сущность.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from monik.domain.enums.base import DomainEnum
from monik.domain.models.transitions import StateTransitionRecord
from monik.services.observability.clock import Clock
from monik.services.observability.context import current_context
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["TransitionLog", "TransitionRecorder"]

_LOGGER = get_logger("services.observability.transitions")


@runtime_checkable
class TransitionLog(Protocol):
    """Журнал переходов состояний."""

    async def record(self, transition: StateTransitionRecord) -> None:
        """Сохранить переход."""
        ...


class TransitionRecorder:
    """Фиксирует переходы состояний в журнале и в structured logs."""

    def __init__(self, log: TransitionLog | None, clock: Clock) -> None:
        self._log = log
        self._clock = clock

    async def record(
        self,
        *,
        entity_type: str,
        entity_id: str,
        to_state: DomainEnum | str,
        from_state: DomainEnum | str | None = None,
        reason: str,
    ) -> StateTransitionRecord:
        """Зафиксировать переход.

        Correlation id берётся из текущего контекста, поэтому событие
        связывается с породившим его workflow
        (``28_OBSERVABILITY.md`` §25).
        """
        context = current_context()
        transition = StateTransitionRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=_state_value(from_state),
            to_state=_state_value(to_state) or "",
            reason=reason,
            occurred_at=self._clock.now(),
            correlation_id=context.correlation_id,
        )
        if self._log is not None:
            await self._log.record(transition)
        _LOGGER.info(
            "state transition",
            extra=log_fields(
                entity_type=entity_type,
                from_state=transition.from_state,
                to_state=transition.to_state,
                reason=reason,
            ),
        )
        return transition


def _state_value(state: DomainEnum | str | None) -> str | None:
    """Строковое значение состояния."""
    if state is None:
        return None
    return state.value if isinstance(state, DomainEnum) else state
