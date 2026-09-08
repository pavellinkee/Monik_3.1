"""Unit-тесты операционных уведомлений.

Проверяется политика alerting (``28_OBSERVABILITY.md`` §59-65):
дедупликация, cooldown, агрегация и отсутствие сообщений при нормальной
работе. Реальный Telegram API и реальные credentials не используются.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from monik.config.sections.notifications import SystemNotificationConfig
from monik.domain.enums.health import ApplicationHealthStatus, ProviderHealthStatus
from monik.domain.enums.notifications import (
    DeliveryErrorKind,
    DestinationKind,
    StartupKind,
)
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import NetworkError
from monik.domain.models.health import ApplicationHealth, ComponentHealth, ProviderHealth
from monik.domain.models.notification import NotificationDestination
from monik.infrastructure.telegram import FakeTransport
from monik.services.notifications import DeliveryReceipt, StartupSummary, SystemNotifier
from monik.services.notifications.system import STARTUP_NOTIFIED_KEY
from monik.services.observability import FakeClock
from tests import factories as f

DESTINATION = NotificationDestination(
    destination_id="MONIK_TELEGRAM_CHAT_ID", kind=DestinationKind.TELEGRAM
)


class MemoryState:
    """Хранилище отметок, переживающее «рестарт» в тестах."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, *, updated_at: datetime) -> None:
        self.values[key] = value


class RaisingTransport:
    """Транспорт, всегда падающий с сетевой ошибкой."""

    def __init__(self) -> None:
        self.attempts = 0

    async def send(self, message: object) -> DeliveryReceipt:
        self.attempts += 1
        raise NetworkError("telegram unreachable", code="http_transport_error")


def _health(
    *,
    status: ApplicationHealthStatus = ApplicationHealthStatus.HEALTHY,
    providers: tuple[ProviderHealth, ...] = (),
    components: tuple[ComponentHealth, ...] = (),
) -> ApplicationHealth:
    return ApplicationHealth(
        status=status, observed_at=f.NOW, providers=providers, components=components
    )


def _provider(
    status: ProviderHealthStatus,
    *,
    failures: int = 0,
    reason: str | None = None,
    provider_id: ProviderId = ProviderId.UNISWAP,
) -> ProviderHealth:
    return ProviderHealth(
        provider_id=provider_id,
        status=status,
        observed_at=f.NOW,
        consecutive_failures=failures,
        reason=reason,
    )


def _component(name: str, status: ApplicationHealthStatus) -> ComponentHealth:
    return ComponentHealth(component=name, status=status, observed_at=f.NOW)


def _notifier(
    transport: object,
    clock: FakeClock,
    *,
    state: MemoryState | None = None,
    **overrides: object,
) -> SystemNotifier:
    return SystemNotifier(
        SystemNotificationConfig(**overrides),  # type: ignore[arg-type]
        transport=transport,  # type: ignore[arg-type]
        destination=DESTINATION,
        clock=clock,
        state=state,
    )


def _summary(**overrides: object) -> StartupSummary:
    base: dict[str, object] = {
        "kind": StartupKind.INITIAL,
        "version": "0.1.0",
        "environment": "production",
        "network": "polygon",
        "providers": ("oneinch", "zero_x"),
        "health": _health(),
    }
    base.update(overrides)
    return StartupSummary(**base)  # type: ignore[arg-type]


class TestStartupNotification:
    async def test_healthy_startup_reports_success(self) -> None:
        transport = FakeTransport()
        assert await _notifier(transport, FakeClock(f.NOW)).notify_startup(_summary())
        text = transport.sent[0].text
        assert text.startswith("🟢")
        assert "0.1.0" in text
        assert "production" in text
        assert "polygon" in text
        assert "oneinch" in text

    async def test_degraded_startup_reports_warning(self) -> None:
        transport = FakeTransport()
        summary = _summary(health=_health(status=ApplicationHealthStatus.DEGRADED))
        await _notifier(transport, FakeClock(f.NOW)).notify_startup(summary)
        assert transport.sent[0].text.startswith("🟠")
        assert "предупреждениями" in transport.sent[0].text

    async def test_unavailable_startup_reports_critical(self) -> None:
        transport = FakeTransport()
        summary = _summary(health=_health(status=ApplicationHealthStatus.UNAVAILABLE))
        await _notifier(transport, FakeClock(f.NOW)).notify_startup(summary)
        assert transport.sent[0].text.startswith("🔴")
        assert "критическими" in transport.sent[0].text

    @pytest.mark.parametrize(
        ("kind", "expected"),
        [
            (StartupKind.INITIAL, "запущен"),
            (StartupKind.RESTART, "перезапущен"),
            (StartupKind.CRASH_RECOVERY, "аварийного завершения"),
        ],
    )
    async def test_startup_kind_is_distinguished(self, kind: StartupKind, expected: str) -> None:
        transport = FakeTransport()
        await _notifier(transport, FakeClock(f.NOW)).notify_startup(_summary(kind=kind))
        assert expected in transport.sent[0].text

    async def test_crash_loop_is_throttled_across_restarts(self) -> None:
        """Отметка переживает рестарт, поэтому цикл падений не спамит."""
        state = MemoryState()
        clock = FakeClock(f.NOW)
        first = FakeTransport()
        assert await _notifier(first, clock, state=state).notify_startup(_summary())

        # Новый процесс через минуту: notifier создан заново, отметка та же.
        clock.advance(timedelta(minutes=1))
        second = FakeTransport()
        assert not await _notifier(second, clock, state=state).notify_startup(_summary())
        assert second.sent == []

    async def test_startup_notification_resumes_after_the_interval(self) -> None:
        state = MemoryState()
        clock = FakeClock(f.NOW)
        await _notifier(FakeTransport(), clock, state=state).notify_startup(_summary())
        clock.advance(timedelta(hours=1))
        transport = FakeTransport()
        assert await _notifier(transport, clock, state=state).notify_startup(_summary())

    async def test_undelivered_startup_does_not_consume_the_cooldown(self) -> None:
        """Неотправленное сообщение не должно закрывать окно следующему."""
        state = MemoryState()
        rejecting = FakeTransport(
            receipt=DeliveryReceipt(delivered=False, error_kind=DeliveryErrorKind.NETWORK_ERROR)
        )
        assert not await _notifier(rejecting, FakeClock(f.NOW), state=state).notify_startup(
            _summary()
        )
        assert STARTUP_NOTIFIED_KEY not in state.values

    async def test_startup_can_be_disabled(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW), startup=False)
        assert not await notifier.notify_startup(_summary())
        assert transport.sent == []

    async def test_transport_failure_does_not_break_startup(self) -> None:
        transport = RaisingTransport()
        assert not await _notifier(transport, FakeClock(f.NOW)).notify_startup(_summary())
        assert transport.attempts == 1


class TestProviderHealthNotifications:
    async def test_healthy_state_produces_no_message(self) -> None:
        """Нормальная работа не создаёт уведомлений."""
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        health = _health(providers=(_provider(ProviderHealthStatus.HEALTHY),))
        assert await notifier.notify_health(health) == ()
        assert await notifier.notify_health(health) == ()
        assert transport.sent == []

    async def test_degradation_is_reported_once(self) -> None:
        """Сотня одинаковых ошибок не превращается в сотню сообщений."""
        transport = FakeTransport()
        clock = FakeClock(f.NOW)
        notifier = _notifier(transport, clock)
        for failures in range(1, 101):
            await notifier.notify_health(
                _health(
                    providers=(
                        _provider(
                            ProviderHealthStatus.DEGRADED,
                            failures=failures,
                            reason="http_server_error",
                        ),
                    )
                )
            )
        assert len(transport.sent) == 1
        assert transport.sent[0].text.startswith("🟠")
        assert "http_server_error" in transport.sent[0].text

    async def test_repeated_state_is_aggregated_after_the_interval(self) -> None:
        transport = FakeTransport()
        clock = FakeClock(f.NOW)
        notifier = _notifier(transport, clock, repeat_interval_seconds=3600)
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=3),))
        )
        clock.advance(timedelta(hours=1))
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=140),))
        )
        assert len(transport.sent) == 2
        assert "137 ошибок" in transport.sent[1].text
        assert "всё ещё" in transport.sent[1].text

    async def test_recovery_is_reported(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=4),))
        )
        await notifier.notify_health(_health(providers=(_provider(ProviderHealthStatus.HEALTHY),)))
        assert len(transport.sent) == 2
        assert transport.sent[1].text.startswith("🟢")
        assert "восстановлен" in transport.sent[1].text

    async def test_state_change_is_reported_within_the_interval(self) -> None:
        """Cooldown подавляет повторы, но не смену состояния."""
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW), repeat_interval_seconds=3600)
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.DEGRADED, failures=2),))
        )
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=4),))
        )
        assert len(transport.sent) == 2
        assert transport.sent[1].text.startswith("🔴")

    async def test_providers_are_reported_separately(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        await notifier.notify_health(
            _health(
                providers=(
                    _provider(ProviderHealthStatus.UNAVAILABLE, failures=4),
                    _provider(ProviderHealthStatus.HEALTHY, provider_id=ProviderId.ONEINCH),
                )
            )
        )
        assert len(transport.sent) == 1
        assert "uniswap" in transport.sent[0].text
        assert "oneinch" not in transport.sent[0].text

    async def test_state_after_startup_is_not_repeated(self) -> None:
        """Состояние, показанное в сообщении о запуске, не дублируется."""
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        health = _health(
            status=ApplicationHealthStatus.DEGRADED,
            providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=4),),
        )
        await notifier.notify_startup(_summary(health=health))
        assert await notifier.notify_health(health) == ()
        assert len(transport.sent) == 1


class TestComponentHealthNotifications:
    async def test_component_failure_is_reported(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        await notifier.notify_health(
            _health(components=(_component("database", ApplicationHealthStatus.UNAVAILABLE),))
        )
        assert transport.sent[0].text.startswith("🔴")
        assert "database" in transport.sent[0].text

    async def test_healthy_components_are_silent(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        components = tuple(
            _component(name, ApplicationHealthStatus.HEALTHY)
            for name in ("level1", "level2", "database")
        )
        assert await notifier.notify_health(_health(components=components)) == ()
        assert transport.sent == []

    async def test_health_notifications_can_be_disabled(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW), health=False)
        await notifier.notify_health(
            _health(components=(_component("database", ApplicationHealthStatus.UNAVAILABLE),))
        )
        assert transport.sent == []

    async def test_disabled_subsystem_sends_nothing_at_all(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW), enabled=False)
        await notifier.notify_startup(_summary())
        await notifier.notify_health(
            _health(providers=(_provider(ProviderHealthStatus.UNAVAILABLE, failures=4),))
        )
        assert transport.sent == []


class TestSecurity:
    async def test_messages_carry_no_credentials(self) -> None:
        transport = FakeTransport()
        notifier = _notifier(transport, FakeClock(f.NOW))
        await notifier.notify_startup(_summary())
        await notifier.notify_health(
            _health(
                providers=(
                    _provider(
                        ProviderHealthStatus.UNAVAILABLE,
                        failures=4,
                        reason="http_authentication_failed",
                    ),
                )
            )
        )
        joined = "\n".join(message.text for message in transport.sent)
        for forbidden in ("api_key", "bot_token", "x-api-key", "Authorization", "chat_id"):
            assert forbidden not in joined

    async def test_system_message_has_no_details_button(self) -> None:
        """Кнопка ``об`` относится к уведомлению о возможности."""
        transport = FakeTransport()
        await _notifier(transport, FakeClock(f.NOW)).notify_startup(_summary())
        assert transport.sent[0].details_callback is None
