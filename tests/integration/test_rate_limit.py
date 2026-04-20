"""Integration tests: rate limit simulation."""

import httpx
import pytest

from testcontainers_atproto import CreateSession, PDSContainer

pytestmark = pytest.mark.requires_docker


class TestRateLimitExhaustion:
    """Exhaust the rate limit budget and verify the PDS returns 429."""

    def test_exhausted_create_session_returns_429(self):
        with PDSContainer(rate_limits=True) as pds:
            account = pds.create_account("alice.test")
            target = CreateSession(account.handle, "password")

            pds.exhaust_rate_limit_budget(target)

            # The next call — without bypass — should be rate-limited.
            resp = httpx.post(
                f"{pds.base_url}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": account.handle,
                    "password": "password",
                },
                timeout=10.0,
            )
            assert resp.status_code == 429

    def test_429_response_body(self):
        with PDSContainer(rate_limits=True) as pds:
            account = pds.create_account("bob.test")
            target = CreateSession(account.handle, "password")

            pds.exhaust_rate_limit_budget(target)

            resp = httpx.post(
                f"{pds.base_url}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": account.handle,
                    "password": "password",
                },
                timeout=10.0,
            )
            body = resp.json()
            assert body["error"] == "RateLimitExceeded"

    def test_429_response_headers(self):
        with PDSContainer(rate_limits=True) as pds:
            account = pds.create_account("carol.test")
            target = CreateSession(account.handle, "password")

            pds.exhaust_rate_limit_budget(target)

            resp = httpx.post(
                f"{pds.base_url}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": account.handle,
                    "password": "password",
                },
                timeout=10.0,
            )
            assert "ratelimit-limit" in resp.headers
            assert "ratelimit-remaining" in resp.headers
            assert "ratelimit-reset" in resp.headers

    def test_bypass_header_avoids_rate_limit(self):
        """Internal calls with the bypass header are never rate-limited."""
        with PDSContainer(rate_limits=True) as pds:
            account = pds.create_account("dave.test", password="hunter2")
            target = CreateSession(account.handle, "hunter2")

            pds.exhaust_rate_limit_budget(target)

            # The same call WITH the bypass header should still succeed.
            resp = httpx.post(
                f"{pds.base_url}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": account.handle,
                    "password": "hunter2",
                },
                headers={"x-ratelimit-bypass": pds.bypass_key},
                timeout=10.0,
            )
            assert resp.status_code == 200
