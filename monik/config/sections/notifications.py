"""Конфигурация уведомлений."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from monik.config.base import ConfigSection
from monik.config.secrets import SecretRef
from monik.domain.enums.notifications import NotificationMode

__all__ = ["NotificationConfig", "NotificationModeRules", "TelegramConfig"]


class NotificationModeRules(ConfigSection):
    """Правила отправки одного режима (``01_PROJECT_REQUIREMENTS.md`` §54).

    Конкретное поведение режима определяется configuration policy, а не
    зашито в код. Режим влияет **только** на правила отправки и не изменяет
    алгоритмы Level 1 / Level 2 (``CLAUDE.md`` §38).

    Порог прибыльности здесь отсутствует намеренно: он принадлежит
    Profit Calculator (``09_PROFIT_CALCULATOR.md`` §2, §30), и второй
    источник истины для него создавать нельзя.
    """

    send_confirmed: bool = True
    send_partial: bool = True


class TelegramConfig(ConfigSection):
    """Параметры Telegram (``17_CONFIGURATION.md`` §46).

    Bot token и chat id задаются только ссылками на environment; реальные
    значения в repository не попадают.
    """

    enabled: bool = False
    bot_token: SecretRef | None = None
    chat_id: SecretRef | None = None
    api_base_url: str = Field(default="https://api.telegram.org", max_length=256)
    request_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    commands_enabled: bool = True
    poll_interval_seconds: float = Field(default=2.0, gt=0, le=60)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if not self.api_base_url.startswith("https://"):
            raise ValueError("telegram api_base_url must use https")
        if self.enabled:
            if self.bot_token is None:
                raise ValueError("telegram is enabled but bot_token reference is missing")
            if self.chat_id is None:
                raise ValueError("telegram is enabled but chat_id reference is missing")
        return self


class NotificationConfig(ConfigSection):
    """Общие параметры уведомлений (``17_CONFIGURATION.md`` §45).

    Режим ``A``/``B`` влияет только на правила отправки и не изменяет
    алгоритмы Level 1 и Level 2 (``CLAUDE.md`` §38).

    По умолчанию уведомления выключены: включать доставку без явно
    настроенного destination было бы опасным default'ом
    (``17_CONFIGURATION.md`` §13).
    """

    enabled: bool = False
    mode: NotificationMode = NotificationMode.A
    language: str = Field(default="ru", min_length=2, max_length=8)
    decimal_places: int = Field(default=6, ge=0, le=18)
    queue_capacity: int = Field(default=500, ge=1, le=100_000)
    max_attempts: int = Field(default=5, ge=1, le=20)
    retry_initial_delay_seconds: float = Field(default=2.0, gt=0, le=300)
    retry_max_delay_seconds: float = Field(default=300.0, gt=0, le=3600)
    deduplication_window_seconds: int = Field(default=3600, ge=0, le=86_400)
    show_calculation_version: bool = False
    mode_a: NotificationModeRules = NotificationModeRules()
    mode_b: NotificationModeRules = NotificationModeRules()
    telegram: TelegramConfig = TelegramConfig()

    def rules_for(self, mode: NotificationMode) -> NotificationModeRules:
        """Правила отправки выбранного режима."""
        return self.mode_a if mode is NotificationMode.A else self.mode_b

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.retry_initial_delay_seconds > self.retry_max_delay_seconds:
            raise ValueError("retry_initial_delay_seconds must not exceed retry_max_delay_seconds")
        if self.enabled and not self.telegram.enabled:
            raise ValueError(
                "notifications are enabled but no destination is configured; "
                "enable telegram or disable notifications"
            )
        return self
