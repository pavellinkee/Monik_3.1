"""Адаптер 0x обязан проходить общий contract suite."""

from __future__ import annotations

from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError
from monik.infrastructure.http import FakeHttpClient
from monik.infrastructure.providers import AggregatorAdapter
from monik.infrastructure.providers.zero_x import ZeroXAdapter
from monik.services.observability import FakeClock
from tests.unit.providers.support import (
    http_returning,
    provider_config,
    resource_manager,
    secret,
)

from .adapter_contract import AdapterContractTests

PRICE_PAYLOAD = {
    "buyAmount": "5140000000000000000",
    "sellAmount": "100000000",
    "gas": "180000",
    "route": {"fills": [{"source": "QuickSwap_V3"}]},
}


class TestZeroXContract(AdapterContractTests):
    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return ZeroXAdapter(
            provider_config(ProviderId.ZERO_X),
            http=http_returning(PRICE_PAYLOAD),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )

    def expected_provider(self) -> ProviderId:
        return ProviderId.ZERO_X

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return ZeroXAdapter(
            provider_config(ProviderId.ZERO_X),
            http=FakeHttpClient([ProviderError("upstream unavailable")] * 5),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )
