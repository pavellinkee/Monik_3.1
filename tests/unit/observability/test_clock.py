"""Тесты абстракции времени."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from monik.services.observability import Clock, FakeClock, SystemClock

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_system_clock_satisfies_protocol() -> None:
    assert isinstance(SystemClock(), Clock)


def test_fake_clock_satisfies_protocol() -> None:
    assert isinstance(FakeClock(START), Clock)


def test_system_clock_returns_utc_aware_time() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fake_clock_does_not_move_on_its_own() -> None:
    """Тесты должны быть детерминированными (23 §17-18)."""
    clock = FakeClock(START)
    assert clock.now() == START
    assert clock.now() == START


def test_fake_clock_advances_explicitly() -> None:
    clock = FakeClock(START)
    clock.advance(timedelta(minutes=5))
    assert clock.now() == START + timedelta(minutes=5)
    assert clock.monotonic() == 300.0


def test_fake_clock_set_to() -> None:
    clock = FakeClock(START)
    clock.set_to(START + timedelta(hours=1))
    assert clock.now() == START + timedelta(hours=1)
    assert clock.monotonic() == 3600.0


def test_fake_clock_rejects_backwards_movement() -> None:
    clock = FakeClock(START)
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError, match="backwards"):
        clock.set_to(START - timedelta(seconds=1))


def test_fake_clock_requires_aware_start() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 1, 1, 12, 0))


def test_fake_clock_normalizes_to_utc() -> None:
    clock = FakeClock(datetime.fromisoformat("2026-01-01T13:00:00+01:00"))
    assert clock.now() == START
