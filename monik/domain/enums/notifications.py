"""Notification System: режимы и типы destination."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class NotificationMode(DomainEnum):
    """Режим уведомлений (``CLAUDE.md`` §38, ``01_PROJECT_REQUIREMENTS.md`` §54).

    Режим влияет **только** на правила отправки уведомлений и не изменяет
    алгоритмы Level 1 / Level 2.
    """

    A = "A"
    B = "B"


class DestinationKind(DomainEnum):
    """Тип канала доставки.

    Destination является configuration/operational identity и не может
    приходить как произвольный внешний ввод (``36_DATA_MODELS.md`` §83).
    """

    TELEGRAM = "telegram"


class DeliveryErrorKind(DomainEnum):
    """Классификация ошибки доставки (``15_NOTIFICATION_SYSTEM.md`` §64).

    Permanent-ошибки не повторяются бесконечно (§65), temporary — могут
    повторяться в пределах лимита (§66).
    """

    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    INVALID_REQUEST = "invalid_request"
    DESTINATION_ERROR = "destination_error"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN_ERROR = "unknown_error"

    @property
    def is_retryable(self) -> bool:
        """Можно ли повторить доставку.

        Неверные credentials, неверный destination и некорректное сообщение
        не исправляются повтором (§65, §67).
        """
        return self in {
            DeliveryErrorKind.RATE_LIMIT,
            DeliveryErrorKind.NETWORK_ERROR,
            DeliveryErrorKind.PROVIDER_ERROR,
            DeliveryErrorKind.UNKNOWN_ERROR,
        }
