"""Диагностическое представление конфигурации.

Позволяет определить загруженную версию, источник, активные сети,
провайдеров, сканеры, расписание и настройки уведомлений
(``17_CONFIGURATION.md`` §57). Секреты заменяются на ``[REDACTED]``
(``17_CONFIGURATION.md`` §58).
"""

from __future__ import annotations

from typing import Any

from monik.config.loader import LoadedConfiguration
from monik.services.observability.redaction import redact_mapping

__all__ = ["configuration_diagnostics"]


def configuration_diagnostics(loaded: LoadedConfiguration) -> dict[str, Any]:
    """Собрать безопасный для логов снимок конфигурации.

    В снимок попадают **имена** переменных окружения, из которых берутся
    credentials, но никогда их значения: имя переменной само по себе
    секретом не является и нужно для диагностики конфигурации.
    """
    config = loaded.config
    telegram = config.notifications.telegram
    summary: dict[str, Any] = {
        "source": loaded.source,
        "version": config.version,
        "environment": config.application.environment.value,
        "timezone": config.application.timezone,
        "networks": [str(network.network_id) for network in config.enabled_networks],
        "providers": [provider.provider_id.value for provider in config.enabled_providers],
        "tokens": len(config.enabled_tokens),
        "scan_tokens": [token.symbol for token in config.scan_tokens()],
        "provider_pairs": [f"{buy.value}->{sell.value}" for buy, sell in config.provider_pairs()],
        "amounts": [str(amount) for amount in config.scanner.amounts],
        "level1": {
            "enabled": config.scanner.level1.enabled,
            "interval_seconds": config.scanner.level1.interval_seconds,
            "top_tokens": config.scanner.level1.top_tokens,
            "overlap_policy": config.scanner.level1.overlap_policy.value,
        },
        "level2": {
            "enabled": config.scanner.level2.enabled,
            "max_parallel": config.scanner.level2.max_parallel,
            "max_attempts": config.scanner.level2.max_attempts,
        },
        "profitability": {
            "metric": config.profitability.threshold_metric.value,
            "final_threshold_percent": str(config.profitability.final_threshold_percent),
            "preliminary_threshold_percent": str(
                config.profitability.preliminary_threshold_percent
            ),
        },
        "scheduler": {
            "enabled": config.scheduler.enabled,
            "tasks": sorted(config.scheduler.tasks),
        },
        "notifications": {
            "enabled": config.notifications.enabled,
            "mode": config.notifications.mode.value,
            "telegram_enabled": telegram.enabled,
            "telegram_bot_env_name": telegram.bot_token.env if telegram.bot_token else None,
            "telegram_chat_env_name": telegram.chat_id.env if telegram.chat_id else None,
        },
        "database": {
            "path": config.database.path,
            "wal_enabled": config.database.wal_enabled,
        },
        "resolved_env_references": len(loaded.secrets),
    }
    return redact_mapping(summary)
