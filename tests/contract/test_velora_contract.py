"""Адаптер Velora обязан проходить общий contract suite."""

from __future__ import annotations

from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError
from monik.infrastructure.http import FakeHttpClient
from monik.infrastructure.providers import AggregatorAdapter
from monik.infrastructure.providers.velora import VeloraAdapter
from monik.services.observability import FakeClock
from tests.unit.providers.support import (
    http_returning,
    provider_config,
    resource_manager,
    secret,
)

from .adapter_contract import AdapterContractTests

PRICE_PAYLOAD = {
    "priceRoute": {
        "srcAmount": "100000000",
        "destAmount": "5140000000000000000",
        "gasCost": "195000",
        "bestRoute": [{"swaps": [{"swapExchanges": [{"exchange": "QuickSwapV3"}]}]}],
    }
}


class TestVeloraContract(AdapterContractTests):
    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return VeloraAdapter(
            provider_config(ProviderId.VELORA),
            http=http_returning(PRICE_PAYLOAD),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )

    def expected_provider(self) -> ProviderId:
        return ProviderId.VELORA

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return VeloraAdapter(
            provider_config(ProviderId.VELORA),
            http=FakeHttpClient([ProviderError("upstream unavailable")] * 5),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )
