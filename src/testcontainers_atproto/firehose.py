# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""FirehoseSubscription: WebSocket subscription to com.atproto.sync.subscribeRepos.

This is a skeleton; method bodies raise :class:`NotImplementedError`.
Requires the ``firehose`` optional dependency group (``websockets``, ``cbor2``).
"""

from __future__ import annotations

from typing import AsyncIterator


class FirehoseSubscription:
    """WebSocket subscription to ``com.atproto.sync.subscribeRepos``."""

    def __init__(self, ws_url: str) -> None:
        self._ws_url = ws_url

    async def events(self, timeout: float = 5.0) -> AsyncIterator[dict]:
        """Yield CBOR-decoded firehose events until ``timeout`` passes with no data."""
        raise NotImplementedError
        # pragma: no cover
        if False:  # pragma: no cover
            yield {}

    def collect(self, count: int, timeout: float = 10.0) -> list[dict]:
        """Synchronously collect up to ``count`` events (or until timeout)."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the WebSocket connection."""
        raise NotImplementedError
