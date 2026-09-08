"""Защита секретов в логах и диагностике.

Секреты не должны попадать в логи ни при каком уровне логирования
(``CLAUDE.md`` §48-49, ``17_CONFIGURATION.md`` §48, §58).

Реализованы два независимых механизма:

1. **Реестр значений** — конфигурация регистрирует фактические значения
   секретов, и любое их вхождение в тексте заменяется на ``[REDACTED]``.
   Это защищает даже при случайной передаче секрета в сообщение об ошибке.
2. **Правила по именам и шаблонам** — ключи вида ``api_key``, ``token``,
   ``authorization`` скрываются по имени, а характерные форматы (Bearer,
   Telegram bot token, приватный ключ) — по шаблону.

Оба механизма применяются к финальному тексту записи лога, поэтому обойти
их из вызывающего кода нельзя.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "REDACTED",
    "SecretRegistry",
    "redact_mapping",
    "redact_text",
    "secret_registry",
]

#: Замена, которая подставляется вместо секрета.
REDACTED = "[REDACTED]"

#: Минимальная длина значения, которое имеет смысл регистрировать.
#: Короткие строки дали бы ложные срабатывания по всему тексту.
_MIN_SECRET_LENGTH = 8

#: Фрагменты имён полей, значения которых считаются секретными.
_SENSITIVE_NAME_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bot_token",
    "credential",
    "password",
    "passwd",
    "private_key",
    "secret",
    "token",
)

#: Имена, которые содержат чувствительный фрагмент, но секретами не являются.
_NAME_EXCEPTIONS = frozenset(
    {
        "token",
        "tokens",
        "token_pair",
        "input_token",
        "output_token",
        "intermediate_token",
        "native_token",
        "token_address",
        "token_symbol",
        "token_amount",
        "token_decimals",
        "from_token",
        "to_token",
        "profit_currency",
        "authenticated",
    }
)

_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization: Bearer <token> / Basic <credentials>
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    # Telegram bot token: <bot_id>:<secret>. Может встречаться внутри URL
    # (".../bot<token>/sendMessage"), поэтому граница слова слева не годится.
    re.compile(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"),
    # Приватный ключ EVM: 0x + 64 hex
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),
    # key=value / key: value для чувствительных имён
    re.compile(
        r"(?i)\b(api[_-]?key|bot[_-]?token|access[_-]?token|secret|password)"
        r"\s*[=:]\s*[\"']?([^\s\"',;}]+)"
    ),
)


def _is_sensitive_name(name: str) -> bool:
    """Считается ли имя поля секретным."""
    normalized = name.strip().lower()
    if normalized in _NAME_EXCEPTIONS:
        return False
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


class SecretRegistry:
    """Реестр фактических значений секретов.

    Значения регистрируются конфигурацией при разрешении секрет-ссылок и
    используются только для того, чтобы вычеркнуть их из вывода. Сам реестр
    не сериализуется и наружу значения не отдаёт.
    """

    def __init__(self) -> None:
        self._values: set[str] = set()

    def register(self, value: str | None) -> None:
        """Зарегистрировать значение секрета.

        Слишком короткие и пустые значения игнорируются: их вычёркивание
        исказило бы обычный текст.
        """
        if not value:
            return
        stripped = value.strip()
        if len(stripped) < _MIN_SECRET_LENGTH:
            return
        self._values.add(stripped)

    def clear(self) -> None:
        """Очистить реестр (используется в тестах и при reload конфигурации)."""
        self._values.clear()

    def contains(self, text: str) -> bool:
        """Содержит ли текст зарегистрированный секрет.

        Нужен там, где секрет нельзя вычёркивать, а можно только отклонить
        значение целиком — например в metric labels
        (``28_OBSERVABILITY.md`` §43).
        """
        return any(value in text for value in self._values)

    def __len__(self) -> int:
        return len(self._values)

    def scrub(self, text: str) -> str:
        """Заменить все зарегистрированные значения на ``[REDACTED]``."""
        if not self._values:
            return text
        result = text
        # Длинные значения заменяются первыми, чтобы вложенные подстроки
        # не разрывали более длинный секрет на фрагменты.
        for value in sorted(self._values, key=len, reverse=True):
            if value in result:
                result = result.replace(value, REDACTED)
        return result


#: Глобальный реестр процесса. Заполняется Configuration subsystem.
secret_registry = SecretRegistry()


def redact_text(text: str, *, registry: SecretRegistry | None = None) -> str:
    """Скрыть секреты в произвольном тексте."""
    active = secret_registry if registry is None else registry
    result = active.scrub(text)
    for pattern in _PATTERNS:
        result = pattern.sub(_replace_match, result)
    return result


def _replace_match(match: re.Match[str]) -> str:
    """Сохранить имя параметра, скрыв его значение."""
    if match.re.groups >= 2 and match.group(1) and match.group(2):
        return f"{match.group(1)}={REDACTED}"
    if match.re.groups >= 1 and match.group(1):
        return f"{match.group(1)} {REDACTED}"
    return REDACTED


def redact_mapping(
    data: dict[str, Any],
    *,
    registry: SecretRegistry | None = None,
) -> dict[str, Any]:
    """Рекурсивно скрыть секретные поля структуры.

    Скрытие выполняется и по имени поля, и по содержимому значения,
    поэтому секрет, попавший в неожиданное поле, всё равно не утечёт.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_name(key):
            result[key] = REDACTED
        else:
            result[key] = _redact_value(value, registry=registry)
    return result


def _redact_value(value: Any, *, registry: SecretRegistry | None) -> Any:
    if isinstance(value, dict):
        return redact_mapping(value, registry=registry)
    if isinstance(value, list):
        return [_redact_value(item, registry=registry) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, registry=registry) for item in value)
    if isinstance(value, str):
        return redact_text(value, registry=registry)
    return value
