"""Тесты нормализованной модели ошибок и их классификации."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from monik.domain.enums import ErrorCategory, ErrorSeverity, Retryability
from monik.domain.errors import (
    AuthenticationError,
    CalculationError,
    CancellationError,
    ConfigurationError,
    DatabaseError,
    DataError,
    DomainValidationError,
    ErrorInfo,
    InternalError,
    MonikError,
    NetworkError,
    ProviderError,
    RateLimitError,
    ResourceError,
    TimeoutError,
    UnsupportedError,
    is_retryable,
)

ALL_ERRORS: tuple[type[MonikError], ...] = (
    AuthenticationError,
    CalculationError,
    CancellationError,
    ConfigurationError,
    DataError,
    DatabaseError,
    DomainValidationError,
    InternalError,
    NetworkError,
    ProviderError,
    RateLimitError,
    ResourceError,
    TimeoutError,
    UnsupportedError,
)


@pytest.mark.parametrize("error_type", ALL_ERRORS, ids=lambda t: t.__name__)
def test_every_error_produces_normalized_info(error_type: type[MonikError]) -> None:
    error = error_type("something went wrong")
    assert isinstance(error, MonikError)
    assert error.info.code
    assert error.info.message == "something went wrong"
    assert isinstance(error.info.category, ErrorCategory)
    assert isinstance(error.info.severity, ErrorSeverity)
    assert isinstance(error.info.retryability, Retryability)


@pytest.mark.parametrize("error_type", ALL_ERRORS, ids=lambda t: t.__name__)
def test_error_codes_are_unique(error_type: type[MonikError]) -> None:
    codes = [candidate.default_code for candidate in ALL_ERRORS]
    assert codes.count(error_type.default_code) == 1


class TestClassification:
    def test_data_error_is_never_retryable(self) -> None:
        """Data error не превращается в валидный результат повтором (CLAUDE.md §12)."""
        error = DataError("malformed response")
        assert not error.is_retryable
        assert not is_retryable(error.info, attempts_used=0, max_attempts=3)

    def test_authentication_error_is_not_retryable(self) -> None:
        error = AuthenticationError("invalid credentials")
        assert not is_retryable(error.info, attempts_used=0, max_attempts=3)

    def test_unsupported_is_not_retryable(self) -> None:
        """UNSUPPORTED — это не временный сбой (06 §75)."""
        assert not is_retryable(
            UnsupportedError("network not supported").info, attempts_used=0, max_attempts=3
        )

    def test_timeout_is_retryable(self) -> None:
        assert is_retryable(TimeoutError("timed out").info, attempts_used=0, max_attempts=3)

    def test_rate_limit_is_conditionally_retryable(self) -> None:
        """429 обрабатывается retry-политикой, а не считается провалом (11 §55)."""
        error = RateLimitError("too many requests", retry_after=timedelta(seconds=30))
        assert error.info.retryability is Retryability.CONDITIONAL
        assert is_retryable(error.info, attempts_used=0, max_attempts=3)
        assert error.info.retry_after == timedelta(seconds=30)

    def test_retry_budget_is_respected(self) -> None:
        """Бесконечные повторы запрещены (CLAUDE.md §32)."""
        error = TimeoutError("timed out")
        assert is_retryable(error.info, attempts_used=2, max_attempts=3)
        assert not is_retryable(error.info, attempts_used=3, max_attempts=3)
        assert not is_retryable(error.info, attempts_used=10, max_attempts=3)

    def test_rejects_invalid_budget(self) -> None:
        error = TimeoutError("timed out")
        with pytest.raises(ValueError):
            is_retryable(error.info, attempts_used=0, max_attempts=0)
        with pytest.raises(ValueError):
            is_retryable(error.info, attempts_used=-1, max_attempts=3)

    def test_cancellation_is_informational(self) -> None:
        """Отмена не является сбоем (35 §130)."""
        error = CancellationError("job cancelled")
        assert error.info.severity is ErrorSeverity.INFO
        assert not is_retryable(error.info, attempts_used=0, max_attempts=3)

    def test_critical_persistence_failure_is_critical(self) -> None:
        """Критический сбой persistence ведёт к SAFE_STOP (CLAUDE.md §34)."""
        assert DatabaseError("disk failure").info.severity is ErrorSeverity.CRITICAL


class TestErrorInfo:
    def test_carries_diagnostic_context(self) -> None:
        error = ProviderError(
            "provider rejected request",
            subsystem="level2",
            operation="quote_buy",
            provider_code="SWAP_FAILED",
            http_status=502,
        )
        assert error.info.subsystem == "level2"
        assert error.info.operation == "quote_buy"
        assert error.info.provider_code == "SWAP_FAILED"
        assert error.info.http_status == 502

    def test_rejects_invalid_http_status(self) -> None:
        with pytest.raises(ValidationError):
            ErrorInfo(
                code="x",
                category=ErrorCategory.PROVIDER,
                severity=ErrorSeverity.ERROR,
                retryability=Retryability.RETRYABLE,
                message="m",
                http_status=42,
            )

    def test_is_immutable(self) -> None:
        error = NetworkError("connection reset")
        with pytest.raises(ValidationError):
            error.info.code = "other"  # type: ignore[misc]

    def test_long_message_is_truncated_not_rejected(self) -> None:
        error = ProviderError("x" * 900)
        assert len(error.info.message) == 512

    def test_custom_code_overrides_default(self) -> None:
        assert ProviderError("m", code="oneinch_unavailable").code == "oneinch_unavailable"

    def test_repr_does_not_leak_extra_state(self) -> None:
        assert repr(ConfigurationError("bad config")) == (
            "ConfigurationError(code='configuration_invalid', message='bad config')"
        )
