"""Правила отправки: режимы A и B.

Режим влияет **только** на правила отправки уведомлений и не изменяет
алгоритмы Level 1 и Level 2 (``CLAUDE.md`` §38). Конкретное поведение
каждого режима задаётся configuration policy
(``01_PROJECT_REQUIREMENTS.md`` §54), а не зашито в код.
"""

from __future__ import annotations

from dataclasses import dataclass

from monik.config.sections.notifications import NotificationConfig
from monik.domain.enums.notifications import NotificationMode
from monik.domain.models.confirmation import ConfirmationSnapshot

__all__ = ["SendDecision", "mode_decision"]


@dataclass(frozen=True, slots=True)
class SendDecision:
    """Решение об отправке и его причина."""

    send: bool
    reason: str | None = None


def mode_decision(
    config: NotificationConfig,
    mode: NotificationMode,
    snapshot: ConfirmationSnapshot,
) -> SendDecision:
    """Нужно ли отправлять уведомление в этом режиме.

    Решение принимается по уже подтверждённому снимку: ничего не
    пересчитывается (``15_NOTIFICATION_SYSTEM.md`` §14, §79). Порог
    прибыльности здесь не применяется — он принадлежит Profit Calculator
    (``09_PROFIT_CALCULATOR.md`` §2, §30).
    """
    rules = config.rules_for(mode)
    confirmed = snapshot.confirmed_amounts
    if not confirmed:
        return SendDecision(send=False, reason="no confirmed amount")
    fully_confirmed = len(confirmed) == len(snapshot.amounts)
    if fully_confirmed and not rules.send_confirmed:
        return SendDecision(send=False, reason=f"mode {mode.value} does not send confirmed")
    if not fully_confirmed and not rules.send_partial:
        return SendDecision(
            send=False, reason=f"mode {mode.value} does not send partial confirmations"
        )
    return SendDecision(send=True)
