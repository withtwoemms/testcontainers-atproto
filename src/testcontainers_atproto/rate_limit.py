"""Rate limit testing support for PDSContainer.

Provides a mapping of XRPC endpoints to their rate limit thresholds,
a base class for rate limit exhaustion targets, and concrete targets
for common endpoints.

Rate limit values are sourced from the PDS source code
(``packages/pds/src/api/com/atproto/``). For endpoints with multiple
windows (e.g. ``createSession`` has both 30/5min and 300/day), the
tightest window is stored — that's what triggers first.
"""

from __future__ import annotations

from typing import Dict, Tuple

import httpx

#: Mapping of XRPC NSID → (max_points, window_seconds).
_RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    "com.atproto.server.createSession": (30, 300),
    "com.atproto.server.createAccount": (100, 300),
    "com.atproto.server.resetPassword": (50, 300),
    "com.atproto.server.requestPasswordReset": (15, 3600),
    "com.atproto.server.deleteAccount": (5, 3600),
    "com.atproto.server.requestAccountDelete": (5, 3600),
    "com.atproto.server.requestEmailConfirmation": (5, 3600),
    "com.atproto.server.requestEmailUpdate": (5, 3600),
    "com.atproto.identity.updateHandle": (10, 300),
    "com.atproto.repo.uploadBlob": (1000, 86400),
}


class RateLimitTarget:
    """Base class for rate limit exhaustion targets.

    Subclass and implement :meth:`__call__` to define the XRPC call
    that should be repeated to exhaust the rate limit budget.

    The ``nsid`` class attribute must match an entry in
    :data:`_RATE_LIMITS` (or pass ``threshold`` explicitly to
    :meth:`~PDSContainer.exhaust_rate_limit_budget`).

    Example::

        class MyCustomCall(RateLimitTarget):
            nsid = "com.example.heavyEndpoint"

            def __init__(self, auth: str) -> None:
                self.auth = auth

            def __call__(self, base_url: str) -> httpx.Response:
                return httpx.post(
                    f"{base_url}/xrpc/{self.nsid}",
                    json={...},
                    headers={"Authorization": f"Bearer {self.auth}"},
                    timeout=10.0,
                )
    """

    nsid: str

    def __call__(self, base_url: str) -> httpx.Response:
        """Execute one rate-limit-consuming call against the PDS.

        Args:
            base_url: PDS base URL (e.g. ``http://localhost:53421``).

        Returns:
            The HTTP response.
        """
        raise NotImplementedError


class CreateSession(RateLimitTarget):
    """Exhaust the ``com.atproto.server.createSession`` rate limit.

    Args:
        identifier: Handle or DID to authenticate as.
        password: Account password.
    """

    nsid = "com.atproto.server.createSession"

    def __init__(self, identifier: str, password: str) -> None:
        self.identifier = identifier
        self.password = password

    def __call__(self, base_url: str) -> httpx.Response:
        return httpx.post(
            f"{base_url}/xrpc/{self.nsid}",
            json={
                "identifier": self.identifier,
                "password": self.password,
            },
            timeout=10.0,
        )
