"""Тесты retry-политики и circuit breaker."""

from __future__ import annotations

import random
from datetime import timedelta

import pytest

from monik.config.sections.resources import CircuitBreakerConfig, RetryConfig
from monik.domain.enums.resources import CircuitState
from monik.domain.errors import (
    AuthenticationError,
    DataError,
    RateLimitError,
    TimeoutError,
)
from monik.services.observability import FakeClock
from monik.services.resources import CircuitBreaker, RetryPolicy


class TestRetryPolicy:
    def _policy(self, **overrides: object) -> RetryPolicy:
        config = RetryConfig(
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
            backoff_multiplier=2.0,
            jitter_ratio=0.0,
            **overrides,  # type: ignore[arg-type]
        )
        return RetryPolicy(config, rng=random.Random(1))

    def test_budget_is_limited(self) -> None:
        """Бесконечные повторы запрещены (CLAUDE.md §32)."""
        policy = self._policy()
        error = TimeoutError("slow").info
        assert policy.should_retry(error, attempts_used=1)
        assert policy.should_retry(error, attempts_used=2)
        assert not policy.should_retry(error, attempts_used=3)

    def test_non_retryable_errors_are_not_repeated(self) -> None:
        policy = self._policy()
        assert not policy.should_retry(DataError("bad payload").info, attempts_used=0)
        assert not policy.should_retry(AuthenticationError("no key").info, attempts_used=0)

    def test_exponential_backoff(self) -> None:
        policy = self._policy()
        error = TimeoutError("slow").info
        assert policy.delay_for(error, attempts_used=0) == 1.0
        assert policy.delay_for(error, attempts_used=1) == 2.0
        assert policy.delay_for(error, attempts_used=2) == 4.0

    def test_delay_is_capped(self) -> None:
        policy = self._policy()
        assert policy.delay_for(TimeoutError("slow").info, attempts_used=10) == 10.0

    def test_jitter_stays_within_bounds(self) -> None:
        config = RetryConfig(
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
            backoff_multiplier=2.0,
            jitter_ratio=0.5,
        )
        policy = RetryPolicy(config, rng=random.Random(7))
        error = TimeoutError("slow").info
        for _ in range(50):
            delay = policy.delay_for(error, attempts_used=1)
            assert 1.0 <= delay <= 2.0

    def test_jitter_produces_varied_delays(self) -> None:
        """Одновременные повторы не должны совпадать по времени (12 §26)."""
        config = RetryConfig(jitter_ratio=0.5, initial_delay_seconds=1.0)
        policy = RetryPolicy(config, rng=random.Random(7))
        error = TimeoutError("slow").info
        delays = {policy.delay_for(error, attempts_used=1) for _ in range(20)}
        assert len(delays) > 1

    def test_retry_after_takes_precedence(self) -> None:
        """Указание провайдера важнее расчётной задержки (12 §27)."""
        policy = self._policy()
        error = RateLimitError("slow down", retry_after=timedelta(seconds=42)).info
        assert policy.delay_for(error, attempts_used=0) == 42.0

    def test_retry_after_can_be_disabled_only_by_invalid_config(self) -> None:
        with pytest.raises(ValueError, match="respect_retry_after"):
            RetryConfig(respect_retry_after=False)

    def test_rate_limit_is_retryable(self) -> None:
        policy = self._policy()
        assert policy.should_retry(RateLimitError("429").info, attempts_used=0)


class TestCircuitBreaker:
    def _breaker(self, clock: FakeClock, **overrides: object) -> CircuitBreaker:
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout_seconds=30.0,
            half_open_max_calls=1,
            success_threshold=2,
            **overrides,  # type: ignore[arg-type]
        )
        return CircuitBreaker(config, clock)

    def test_starts_closed(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        assert breaker.state is CircuitState.CLOSED
        assert breaker.allows_request()

    def test_opens_after_threshold(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        for _ in range(3):
            breaker.on_failure()
        assert breaker.state is CircuitState.OPEN
        assert not breaker.allows_request()

    def test_single_failure_does_not_open(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        breaker.on_failure()
        assert breaker.state is CircuitState.CLOSED

    def test_success_resets_failures(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        breaker.on_failure()
        breaker.on_failure()
        breaker.on_success()
        breaker.on_failure()
        assert breaker.state is CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        for _ in range(3):
            breaker.on_failure()
        clock.advance(timedelta(seconds=31))
        assert breaker.state is CircuitState.HALF_OPEN
        assert breaker.allows_request()

    def test_half_open_limits_probe_calls(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        for _ in range(3):
            breaker.on_failure()
        clock.advance(timedelta(seconds=31))
        breaker.on_request_started()
        assert not breaker.allows_request()

    def test_half_open_failure_reopens(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        for _ in range(3):
            breaker.on_failure()
        clock.advance(timedelta(seconds=31))
        breaker.on_request_started()
        breaker.on_failure()
        assert breaker.state is CircuitState.OPEN

    def test_half_open_closes_after_successes(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock)
        for _ in range(3):
            breaker.on_failure()
        clock.advance(timedelta(seconds=31))
        breaker.on_success()
        breaker.on_success()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.allows_request()

    def test_disabled_breaker_always_allows(self, clock: FakeClock) -> None:
        breaker = self._breaker(clock, enabled=False)
        for _ in range(10):
            breaker.on_failure()
        assert breaker.allows_request()
