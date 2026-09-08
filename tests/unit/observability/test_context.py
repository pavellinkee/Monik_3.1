"""Тесты контекста корреляции."""

from __future__ import annotations

import asyncio

import pytest

from monik.services.observability import current_context, log_context


def test_context_is_empty_by_default() -> None:
    assert current_context().as_fields() == {}


def test_context_adds_fields() -> None:
    with log_context(scan_id="scan-1", v_id="#V1"):
        assert current_context().as_fields() == {"scan_id": "scan-1", "v_id": "#V1"}


def test_context_is_restored_after_exit() -> None:
    with log_context(scan_id="scan-1"):
        pass
    assert current_context().scan_id is None


def test_context_is_restored_after_exception() -> None:
    with pytest.raises(RuntimeError), log_context(k_id="#K1"):
        raise RuntimeError("boom")
    assert current_context().k_id is None


def test_nested_context_merges_and_unwinds() -> None:
    with log_context(scan_id="scan-1"):
        with log_context(k_id="#K1"):
            fields = current_context().as_fields()
            assert fields == {"scan_id": "scan-1", "k_id": "#K1"}
        assert current_context().k_id is None


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown correlation fields"):
        with log_context(secret_value="x"):
            pass


def test_values_are_stringified() -> None:
    with log_context(request_id=123):
        assert current_context().request_id == "123"


async def test_context_is_isolated_between_tasks() -> None:
    """Конкурентные корутины не должны видеть чужой контекст."""
    observed: dict[str, str | None] = {}

    async def worker(name: str) -> None:
        with log_context(scan_id=name):
            await asyncio.sleep(0)
            observed[name] = current_context().scan_id

    await asyncio.gather(worker("a"), worker("b"))
    assert observed == {"a": "a", "b": "b"}
    assert current_context().scan_id is None
