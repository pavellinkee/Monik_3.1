"""Тесты allowlist хостов и защиты от SSRF."""

from __future__ import annotations

import pytest

from monik.domain.errors import DomainValidationError
from monik.infrastructure.http import UrlPolicy

POLICY = UrlPolicy({"api.example.com", "api.provider.io"})


class TestAllowedUrls:
    def test_allows_configured_host(self) -> None:
        assert POLICY.validate("https://api.example.com/v1/quote") == "api.example.com"

    def test_host_case_is_normalized(self) -> None:
        assert POLICY.validate("https://API.Example.COM/v1") == "api.example.com"

    def test_is_allowed_helper(self) -> None:
        assert POLICY.is_allowed("https://api.example.com/x")
        assert not POLICY.is_allowed("https://evil.example.net/x")

    def test_with_hosts_extends_policy(self) -> None:
        extended = POLICY.with_hosts(("api.telegram.org",))
        assert extended.is_allowed("https://api.telegram.org/bot/sendMessage")
        assert not POLICY.is_allowed("https://api.telegram.org/bot/sendMessage")


class TestBlockedUrls:
    def test_unknown_host_is_blocked(self) -> None:
        """Произвольный URL из ответа провайдера не запрашивается (06 §80)."""
        with pytest.raises(DomainValidationError, match="not in the allowed hosts"):
            POLICY.validate("https://attacker.example.net/steal")

    def test_http_scheme_is_blocked(self) -> None:
        with pytest.raises(DomainValidationError, match="scheme"):
            POLICY.validate("http://api.example.com/v1")

    @pytest.mark.parametrize("scheme", ["file", "ftp", "gopher", "data"])
    def test_non_https_schemes_are_blocked(self, scheme: str) -> None:
        with pytest.raises(DomainValidationError, match="scheme"):
            POLICY.validate(f"{scheme}://api.example.com/v1")

    def test_credentials_in_url_are_blocked(self) -> None:
        with pytest.raises(DomainValidationError, match="credentials"):
            POLICY.validate("https://user:secret@api.example.com/v1")

    def test_missing_host_is_blocked(self) -> None:
        with pytest.raises(DomainValidationError, match="no host"):
            POLICY.validate("https:///v1/quote")

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "10.0.0.5",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",
            "0.0.0.0",
            "[::1]",
        ],
    )
    def test_internal_addresses_are_blocked(self, host: str) -> None:
        """SSRF во внутреннюю сеть невозможен (32_SECURITY)."""
        policy = UrlPolicy(
            {
                "127.0.0.1",
                "10.0.0.5",
                "192.168.1.1",
                "172.16.0.1",
                "169.254.169.254",
                "0.0.0.0",
                "::1",
            }
        )
        with pytest.raises(DomainValidationError, match="non-public|loopback"):
            policy.validate(f"https://{host}/latest/meta-data")

    def test_localhost_is_blocked_even_if_allowlisted(self) -> None:
        policy = UrlPolicy({"localhost"})
        with pytest.raises(DomainValidationError, match="loopback"):
            policy.validate("https://localhost/admin")

    def test_public_ip_requires_allowlist(self) -> None:
        policy = UrlPolicy({"93.184.216.34"})
        assert policy.validate("https://93.184.216.34/") == "93.184.216.34"
        assert not UrlPolicy(set()).is_allowed("https://93.184.216.34/")

    def test_empty_policy_blocks_everything(self) -> None:
        assert not UrlPolicy(set()).is_allowed("https://api.example.com/x")
