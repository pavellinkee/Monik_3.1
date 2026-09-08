#!/usr/bin/env python3
"""Проверка контрактов провайдерских API против реальных endpoints.

Решение D-3 (``DEVELOPMENT_PLAN.md`` §9): адаптеры реализованы по
документированным контрактам, но не проверены вживую — в среде разработки
провайдерские API заблокированы и ключей нет.

Этот скрипт выполняет реальные запросы и сверяет ответ с ожиданиями
адаптера. Запускать в среде с сетевым доступом и заданными переменными
окружения:

    MONIK_ONEINCH_API_KEY=... \\
    MONIK_ZEROX_API_KEY=... \\
    MONIK_UNISWAP_API_KEY=... \\
    python scripts/verify_provider_api.py --config config/config.yaml

Скрипт **не выполняет свопы** и не изменяет состояние: он только получает
котировки (``01_PROJECT_REQUIREMENTS.md`` §55).

Скрипт не дублирует business logic: он вызывает те же адаптеры, что и
приложение (``25_PROJECT_STRUCTURE.md`` §42).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from decimal import Decimal

from monik.config import LoadedConfiguration, load_configuration
from monik.config.sections.providers import ProviderConfig
from monik.domain.enums.operations import OperationType
from monik.domain.enums.providers import ProviderId
from monik.domain.errors import MonikError
from monik.domain.models.token import Token
from monik.domain.value_objects.identifiers import RequestId
from monik.infrastructure.http import HttpxClient, UrlPolicy
from monik.infrastructure.providers import AggregatorAdapter, QuoteRequest
from monik.infrastructure.providers.oneinch import OneInchAdapter
from monik.infrastructure.providers.uniswap import UniswapAdapter
from monik.infrastructure.providers.velora import VeloraAdapter
from monik.infrastructure.providers.zero_x import ZeroXAdapter
from monik.services.observability import SystemClock, secret_registry
from monik.services.resources import ResourceManager

ADAPTERS = {
    ProviderId.ONEINCH: OneInchAdapter,
    ProviderId.ZERO_X: ZeroXAdapter,
    ProviderId.VELORA: VeloraAdapter,
    ProviderId.UNISWAP: UniswapAdapter,
}


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Итог проверки одного провайдера."""

    provider_id: ProviderId
    ok: bool
    detail: str

    def render(self) -> str:
        """Строка для вывода в консоль."""
        marker = "OK  " if self.ok else "FAIL"
        return f"[{marker}] {self.provider_id.value}: {self.detail}"


def _tokens(loaded: LoadedConfiguration) -> tuple[Token, Token]:
    """Базовый и первый торгуемый токен из конфигурации."""
    config = loaded.config
    base_config = config.token(config.scanner.base_network, config.scanner.base_token_address)
    if base_config is None:
        raise SystemExit("scanner base token is not configured")
    scan_tokens = config.scan_tokens()
    if not scan_tokens:
        raise SystemExit("configuration has no tokens to scan")
    target = scan_tokens[0]
    return (
        Token(
            network_id=base_config.network_id,
            address=base_config.address,
            symbol=base_config.symbol,
            decimals=base_config.decimals,
        ),
        Token(
            network_id=target.network_id,
            address=target.address,
            symbol=target.symbol,
            decimals=target.decimals,
        ),
    )


def _allowed_hosts(loaded: LoadedConfiguration) -> tuple[str, ...]:
    """Хосты, к которым скрипту разрешено обращаться."""
    hosts = {"api.1inch.dev", "api.0x.org", "api.paraswap.io", "trade-api.gateway.uniswap.org"}
    for provider in loaded.config.enabled_providers:
        if provider.base_url:
            hosts.add(provider.base_url.removeprefix("https://").split("/", 1)[0])
    return tuple(sorted(hosts))


def _build_adapter(
    provider: ProviderConfig,
    loaded: LoadedConfiguration,
    resources: ResourceManager,
) -> AggregatorAdapter:
    """Собрать адаптер провайдера с реальным HTTP-клиентом."""
    clock = SystemClock()
    http = HttpxClient(loaded.config.http, UrlPolicy(set(_allowed_hosts(loaded))))
    api_key = loaded.secrets.get(provider.api_key) if provider.api_key else None
    adapter_type = ADAPTERS[provider.provider_id]
    return adapter_type(  # type: ignore[return-value]
        provider,
        http=http,
        resources=resources,
        clock=clock,
        api_key=api_key,
    )


async def _check(
    provider: ProviderConfig,
    loaded: LoadedConfiguration,
    amount: Decimal,
) -> CheckResult:
    """Выполнить одну котировку и проверить её нормализацию."""
    resources = ResourceManager(loaded.config.resources, SystemClock(), rng=random.Random())
    adapter = _build_adapter(provider, loaded, resources)
    base, target = _tokens(loaded)
    request = QuoteRequest(
        network_id=loaded.config.scanner.base_network,
        operation=OperationType.BUY,
        input_token=base,
        output_token=target,
        input_amount=base.amount_from_decimal(str(amount)),
        request_id=RequestId.generate(),
    )
    try:
        quote = await adapter.get_quote(request)
    except MonikError as error:
        return CheckResult(provider.provider_id, False, f"{error.info.code}: {error.info.message}")
    finally:
        await adapter.aclose()

    if quote.output_amount.raw <= 0:
        return CheckResult(provider.provider_id, False, "provider returned a zero output amount")
    return CheckResult(
        provider.provider_id,
        True,
        (
            f"{base.symbol} {amount} -> {target.symbol} "
            f"{quote.output_amount.as_decimal} via {quote.route.steps[0].protocol} "
            f"(routing={quote.route.routing_mode.value}, "
            f"gas={quote.estimated_gas_units})"
        ),
    )


async def _run(config_path: str, amount: Decimal) -> int:
    loaded = load_configuration(config_path, registry=secret_registry)
    results: list[CheckResult] = []
    for provider in loaded.config.enabled_providers:
        if provider.provider_id not in ADAPTERS:
            continue
        results.append(await _check(provider, loaded, amount))

    if not results:
        print("no enabled providers to verify")
        return 1
    for result in results:
        print(result.render())
    failed = [result for result in results if not result.ok]
    print(f"\nverified {len(results) - len(failed)}/{len(results)} providers")
    return 1 if failed else 0


def main() -> int:
    """Точка входа скрипта."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config.yaml", help="path to configuration")
    parser.add_argument("--amount", default="10", help="amount of the base token to quote")
    args = parser.parse_args()
    return asyncio.run(_run(args.config, Decimal(args.amount)))


if __name__ == "__main__":
    sys.exit(main())
