"""Адаптер 1inch обязан проходить общий contract suite."""

from __future__ import annotations

from monik.domain.enums.providers import ProviderId
from monik.domain.errors import ProviderError
from monik.infrastructure.http import FakeHttpClient
from monik.infrastructure.providers import AggregatorAdapter
from monik.infrastructure.providers.oneinch import OneInchAdapter
from monik.services.observability import FakeClock
from tests.unit.providers.support import http_returning, provider_config, resource_manager, secret

from .adapter_contract import AdapterContractTests

QUOTE_PAYLOAD = {
    "dstAmount": "5140000000000000000",
    "gas": 210000,
    "protocols": [[[{"name": "QUICKSWAP_V3", "part": 100}]]],
}


class TestOneInchContract(AdapterContractTests):
    def make_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return OneInchAdapter(
            provider_config(ProviderId.ONEINCH),
            http=http_returning(QUOTE_PAYLOAD),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )

    def expected_provider(self) -> ProviderId:
        return ProviderId.ONEINCH

    def make_failing_adapter(self, clock: FakeClock) -> AggregatorAdapter:
        return OneInchAdapter(
            provider_config(ProviderId.ONEINCH),
            http=FakeHttpClient([ProviderError("upstream unavailable")] * 5),
            resources=resource_manager(clock),
            clock=clock,
            api_key=secret(),
        )
