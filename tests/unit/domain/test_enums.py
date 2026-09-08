"""Тесты стабильности доменных enum'ов.

Значения enum'ов попадают в persistent state, поэтому изменение значения —
breaking change, требующий migration (36 §76-78).
"""

from __future__ import annotations

import pytest

from monik.domain import enums
from monik.domain.enums import (
    AmountConfirmationStatus,
    CapabilityStatus,
    DomainEnum,
    JobStatus,
    NotificationMode,
    OpportunityStatus,
    ProviderId,
    RequestPriority,
)

#: Значения, зафиксированные архитектурой. Изменять только вместе с migration.
FROZEN_VALUES: dict[str, set[str]] = {
    "ProviderId": {"oneinch", "zero_x", "velora", "uniswap"},
    "OperationType": {"buy", "sell"},
    "JobStatus": {
        "queued",
        "running",
        "confirmed",
        "rejected",
        "failed",
        "expired",
        "cancelled",
    },
    "AmountConfirmationStatus": {"confirmed", "unconfirmed", "partial"},
    "NotificationStatus": {
        "queued",
        "sending",
        "retry_wait",
        "sent",
        "failed",
        "cancelled",
    },
    "NotificationMode": {"A", "B"},
    "CircuitState": {"closed", "open", "half_open"},
}


def _enum_types() -> list[type[DomainEnum]]:
    found = []
    for name in enums.__all__:
        attribute = getattr(enums, name)
        if isinstance(attribute, type) and issubclass(attribute, DomainEnum):
            if attribute is not DomainEnum:
                found.append(attribute)
    return found


@pytest.mark.parametrize("enum_name", sorted(FROZEN_VALUES))
def test_frozen_values_are_unchanged(enum_name: str) -> None:
    enum_type = getattr(enums, enum_name)
    assert {member.value for member in enum_type} == FROZEN_VALUES[enum_name]


@pytest.mark.parametrize("enum_type", _enum_types(), ids=lambda t: t.__name__)
def test_values_are_unique_and_non_empty(enum_type: type[DomainEnum]) -> None:
    values = [member.value for member in enum_type]
    assert len(values) == len(set(values))
    assert all(value for value in values)


@pytest.mark.parametrize("enum_type", _enum_types(), ids=lambda t: t.__name__)
def test_is_serializable_as_plain_string(enum_type: type[DomainEnum]) -> None:
    member = next(iter(enum_type))
    assert isinstance(member.value, str)
    assert str(member) == member.value
    assert enum_type(member.value) is member


def test_provider_set_matches_approved_providers() -> None:
    """Набор провайдеров утверждён архитектурой (01 §3)."""
    assert {p.value for p in ProviderId} == {"oneinch", "zero_x", "velora", "uniswap"}


def test_priority_order_is_level2_first() -> None:
    """Level 2 > Level 1 SELL > Level 1 BUY > Maintenance (CLAUDE.md §15)."""
    ordered = sorted(RequestPriority, key=lambda p: p.rank)
    assert ordered == [
        RequestPriority.LEVEL2,
        RequestPriority.LEVEL1_SELL,
        RequestPriority.LEVEL1_BUY,
        RequestPriority.MAINTENANCE,
        RequestPriority.BACKGROUND,
    ]


def test_priority_ranks_are_unique() -> None:
    ranks = [priority.rank for priority in RequestPriority]
    assert len(ranks) == len(set(ranks))


def test_opportunity_lifecycle_covers_verification_and_notification() -> None:
    """Решение D-1: единый lifecycle Opportunity."""
    values = {status.value for status in OpportunityStatus}
    assert {"created", "verifying"} <= values
    assert {"confirmed", "partial", "unprofitable", "route_unavailable"} <= values
    assert {"notified", "notified_partial", "notified_failed"} <= values


def test_capability_has_distinct_unknown_and_unsupported() -> None:
    assert CapabilityStatus.UNKNOWN is not CapabilityStatus.UNSUPPORTED


def test_partial_is_distinct_from_confirmed() -> None:
    assert AmountConfirmationStatus.PARTIAL is not AmountConfirmationStatus.CONFIRMED


def test_notification_mode_values_are_uppercase_letters() -> None:
    assert {mode.value for mode in NotificationMode} == {"A", "B"}


def test_job_status_repr_is_readable() -> None:
    assert repr(JobStatus.QUEUED) == "JobStatus.QUEUED"
