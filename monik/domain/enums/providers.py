"""Идентификаторы поддерживаемых aggregator providers."""

from __future__ import annotations

from monik.domain.enums.base import DomainEnum


class ProviderId(DomainEnum):
    """Утверждённые production providers (``01_PROJECT_REQUIREMENTS.md`` §3).

    Добавление нового provider — отдельное архитектурное решение
    (``39_IMPLEMENTATION_PLAN.md`` §82), а не свободное расширение enum'а.
    """

    ONEINCH = "oneinch"
    ZERO_X = "zero_x"
    VELORA = "velora"
    UNISWAP = "uniswap"
