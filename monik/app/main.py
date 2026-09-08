"""Application entrypoint.

Здесь нет business logic (``25_PROJECT_STRUCTURE.md`` §5): модуль загружает
конфигурацию, собирает приложение и передаёт управление его жизненному
циклу.

Порядок запуска соответствует ``CLAUDE.md`` §30.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys
from collections.abc import Sequence

from monik.app.lifecycle import Application, create_application
from monik.config import configuration_diagnostics, load_configuration
from monik.domain.enums.health import SupervisorState
from monik.domain.errors import MonikError
from monik.services.observability import configure_logging, secret_registry
from monik.services.observability.clock import SystemClock
from monik.services.observability.logging import get_logger, log_fields

__all__ = ["main", "run"]

_LOGGER = get_logger("app.main")

#: Код возврата при аварийной остановке.
_EXIT_SAFE_STOP = 2

#: Код возврата при ошибке конфигурации или запуска.
_EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    """Аргументы командной строки."""
    parser = argparse.ArgumentParser(prog="monik", description="Monik DEX arbitrage scanner")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="path to the configuration file",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate the configuration and exit without starting workers",
    )
    return parser


async def _run(config_path: str, *, check_only: bool) -> int:
    """Загрузить конфигурацию и выполнить жизненный цикл приложения."""
    loaded = load_configuration(config_path, registry=secret_registry)
    configure_logging(level=loaded.config.logging.level.value, registry=secret_registry)
    _LOGGER.info("configuration loaded", extra=log_fields(**configuration_diagnostics(loaded)))
    if check_only:
        return 0

    application, database = await create_application(loaded, clock=SystemClock())
    try:
        await application.startup()
        _install_signal_handlers(application)
        state = await application.run()
    finally:
        await application.shutdown()
        await database.close()

    if state is SupervisorState.SAFE_STOP:
        _LOGGER.error("application stopped in SAFE_STOP")
        return _EXIT_SAFE_STOP
    return 0


def _install_signal_handlers(application: Application) -> None:
    """Остановка по SIGINT/SIGTERM выполняется graceful (``14`` §49)."""
    loop = asyncio.get_running_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        handled = getattr(signal, signal_name, None)
        if handled is None:  # pragma: no cover - платформа без сигнала
            continue
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(handled, application.request_stop)


def main(argv: Sequence[str] | None = None) -> int:
    """Запустить приложение и вернуть код возврата."""
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(arguments.config, check_only=arguments.check_config))
    except MonikError as error:
        # Ошибка нормализована: наружу не выходит трассировка библиотеки.
        sys.stderr.write(f"monik: {error.info.code}: {error.info.message}\n")
        return _EXIT_ERROR
    except KeyboardInterrupt:  # pragma: no cover - интерактивное прерывание
        return 0


def run() -> int:
    """Console entrypoint ``monik``."""
    return main()


if __name__ == "__main__":  # pragma: no cover - тонкая обёртка
    raise SystemExit(run())
