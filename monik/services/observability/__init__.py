"""Clock, structured logging, correlation context и защита секретов.

Подсистема не содержит business logic: она предоставляет средства, которыми
пользуются остальные слои.
"""

from monik.services.observability.clock import Clock, FakeClock, SystemClock
from monik.services.observability.context import (
    CorrelationContext,
    current_context,
    log_context,
)
from monik.services.observability.events import TransitionLog, TransitionRecorder
from monik.services.observability.logging import (
    StructuredFormatter,
    configure_logging,
    get_logger,
    log_fields,
)
from monik.services.observability.metrics import (
    ALLOWED_LABELS,
    MetricSample,
    MetricsRegistry,
    TimingStats,
)
from monik.services.observability.redaction import (
    REDACTED,
    SecretRegistry,
    redact_mapping,
    redact_text,
    secret_registry,
)

__all__ = [
    "ALLOWED_LABELS",
    "REDACTED",
    "Clock",
    "CorrelationContext",
    "FakeClock",
    "MetricSample",
    "MetricsRegistry",
    "SecretRegistry",
    "StructuredFormatter",
    "SystemClock",
    "TimingStats",
    "TransitionLog",
    "TransitionRecorder",
    "configure_logging",
    "current_context",
    "get_logger",
    "log_context",
    "log_fields",
    "redact_mapping",
    "redact_text",
    "secret_registry",
]
