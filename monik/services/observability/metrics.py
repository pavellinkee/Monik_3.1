"""Метрики Monik.

Метрики отражают численные и агрегируемые характеристики системы
(``28_OBSERVABILITY.md`` §28-29).

Два жёстких ограничения:

* labels ограничены и предсказуемы (§41): идентификаторы возможностей,
  задач, адреса токенов и произвольный текст в label не попадают (§42);
* ни labels, ни значения не содержат секретов (§43): значение,
  зарегистрированное как секрет, отклоняется.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from monik.services.observability.redaction import SecretRegistry

__all__ = ["ALLOWED_LABELS", "MetricSample", "MetricsRegistry", "TimingStats"]

#: Допустимые имена label: только low-cardinality измерения
#: (``28_OBSERVABILITY.md`` §44-47).
ALLOWED_LABELS = frozenset(
    {
        "provider",
        "network",
        "operation",
        "status",
        "component",
        "task",
        "kind",
        "outcome",
    }
)

#: Имена, создающие high cardinality (``28_OBSERVABILITY.md`` §42).
FORBIDDEN_LABELS = frozenset(
    {
        "opportunity_id",
        "job_id",
        "k_id",
        "v_id",
        "scan_id",
        "request_id",
        "notification_id",
        "token",
        "address",
        "url",
        "message",
        "text",
    }
)

#: Максимальная длина значения label: длинные значения почти всегда
#: означают идентификатор или произвольный текст.
_MAX_LABEL_VALUE = 64


@dataclass(frozen=True, slots=True)
class MetricSample:
    """Значение метрики с набором labels."""

    name: str
    labels: tuple[tuple[str, str], ...]
    value: float


@dataclass
class TimingStats:
    """Агрегированная длительность операции."""

    count: int = 0
    total_seconds: float = 0.0
    min_seconds: float | None = None
    max_seconds: float | None = None

    def observe(self, seconds: float) -> None:
        """Учесть одно измерение."""
        self.count += 1
        self.total_seconds += seconds
        self.min_seconds = seconds if self.min_seconds is None else min(self.min_seconds, seconds)
        self.max_seconds = seconds if self.max_seconds is None else max(self.max_seconds, seconds)

    @property
    def average_seconds(self) -> float | None:
        """Средняя длительность либо ``None``, если измерений не было."""
        if self.count == 0:
            return None
        return self.total_seconds / self.count


@dataclass
class MetricsRegistry:
    """Счётчики и длительности с проверкой labels."""

    secrets: SecretRegistry | None = None
    counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = field(default_factory=dict)
    timings: dict[tuple[str, tuple[tuple[str, str], ...]], TimingStats] = field(
        default_factory=dict
    )
    gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = field(default_factory=dict)

    def increment(self, name: str, *, amount: int = 1, **labels: str) -> None:
        """Увеличить счётчик."""
        key = (name, self._labels(labels))
        self.counters[key] = self.counters.get(key, 0) + amount

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        """Учесть длительность операции."""
        key = (name, self._labels(labels))
        stats = self.timings.setdefault(key, TimingStats())
        stats.observe(seconds)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Задать текущее значение (например глубину очереди)."""
        self.gauges[(name, self._labels(labels))] = value

    def counter(self, name: str, **labels: str) -> int:
        """Текущее значение счётчика."""
        return self.counters.get((name, self._labels(labels)), 0)

    def timing(self, name: str, **labels: str) -> TimingStats | None:
        """Агрегированная длительность."""
        return self.timings.get((name, self._labels(labels)))

    def gauge(self, name: str, **labels: str) -> float | None:
        """Текущее значение gauge."""
        return self.gauges.get((name, self._labels(labels)))

    def samples(self) -> tuple[MetricSample, ...]:
        """Снимок всех метрик в детерминированном порядке."""
        collected = [
            MetricSample(name=name, labels=labels, value=float(value))
            for (name, labels), value in self.counters.items()
        ]
        collected.extend(
            MetricSample(name=name, labels=labels, value=value)
            for (name, labels), value in self.gauges.items()
        )
        collected.extend(
            MetricSample(name=f"{name}_seconds_total", labels=labels, value=stats.total_seconds)
            for (name, labels), stats in self.timings.items()
        )
        return tuple(sorted(collected, key=lambda sample: (sample.name, sample.labels)))

    def reset(self) -> None:
        """Очистить накопленные значения."""
        self.counters.clear()
        self.timings.clear()
        self.gauges.clear()

    # --- внутреннее -------------------------------------------------------

    def _labels(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """Проверить и нормализовать labels."""
        for name, value in labels.items():
            if name in FORBIDDEN_LABELS:
                raise ValueError(f"metric label {name!r} creates high cardinality")
            if name not in ALLOWED_LABELS:
                raise ValueError(f"metric label {name!r} is not allowed")
            if len(value) > _MAX_LABEL_VALUE:
                raise ValueError(f"metric label {name!r} value is too long")
            if self.secrets is not None and self.secrets.contains(value):
                raise ValueError(f"metric label {name!r} must not contain a secret")
        return tuple(sorted(labels.items()))
