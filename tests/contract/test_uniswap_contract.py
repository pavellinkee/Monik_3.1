"""Адаптер Uniswap обязан проходить общий contract suite."""

from __future__ import annotations

from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError
from monik.infrastructure.http import FakeHttpClient
from monik.infrastructure.providers import AggregatorAdapter
from monik.infrastructure.providers.uniswap import UniswapAdapter
from monik.services.observability import FakeClock
from tests.unit.providers.support import (
    http_returning,
    provider_config,
    resource_manager,
    secret,
)

from .adapter_contract import AdapterContractTests

CLASSIC_PAYLOAD = {
    "routing": "CLASSIC",
    "quote": {
        "output": {"amount": "5140000000000000000"},
        "gasUseEstimate": "230000",
        "route": [[{"type": "v3-pool", "address": "0xpool1"}]],
    },
}


class TestUniswapContract(AdapterContractTests):
    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return UniswapAdapter(
            provider_config(ProviderId.UNISWAP),
            http=http_returning(CLASSIC_PAYLOAD),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )

    def expected_provider(self) -> ProviderId:
        return ProviderId.UNISWAP

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return UniswapAdapter(
            provider_config(ProviderId.UNISWAP),
            http=FakeHttpClient([ProviderError("upstream unavailable")] * 5),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )
