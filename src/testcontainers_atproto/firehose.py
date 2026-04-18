"""FirehoseSubscription: WebSocket client for com.atproto.sync.subscribeRepos.

Requires the ``firehose`` optional dependency group (``websockets``, ``cbor2``).
Install with: ``pip install testcontainers-atproto[firehose]``
"""

from __future__ import annotations

import asyncio
import io
from typing import AsyncIterator

try:
    import cbor2
    import websockets
    _HAS_FIREHOSE_DEPS = True
except ImportError:
    _HAS_FIREHOSE_DEPS = False


def _check_deps() -> None:
    """Raise :class:`ImportError` with actionable message if firehose deps are missing."""
    if not _HAS_FIREHOSE_DEPS:
        raise ImportError(
            "Firehose support requires the 'firehose' extra. "
            "Install it with: pip install testcontainers-atproto[firehose]"
        )


def _decode_frame(data: bytes) -> dict:
    """Decode a binary firehose frame into header + body dicts.

    Each frame contains two concatenated CBOR values:
    1. Header: ``{"op": 1, "t": "#commit"}`` (or ``#handle``, ``#identity``, etc.)
    2. Body: ``{"repo": "did:plc:...", "ops": [...], "seq": N, ...}``
    """
    buf = io.BytesIO(data)
    decoder = cbor2.CBORDecoder(buf)
    header = decoder.decode()
    body = decoder.decode()
    return {"header": header, "body": body}


class FirehoseSubscription:
    """WebSocket subscription to ``com.atproto.sync.subscribeRepos``."""

    def __init__(self, ws_url: str) -> None:
        self._ws_url = ws_url
        self._ws = None

    async def _connect(self):
        """Establish the WebSocket connection if not already open."""
        _check_deps()
        if self._ws is None:
            self._ws = await websockets.connect(self._ws_url)
        return self._ws

    async def events(self, timeout: float = 5.0) -> AsyncIterator[dict]:
        """Yield CBOR-decoded firehose events until *timeout* passes with no data.

        Each yielded dict has the shape ``{"header": {...}, "body": {...}}``.
        The header contains ``op`` and ``t`` fields.  The body contains
        ``repo``, ``ops``, ``seq``, ``blocks``, and other commit fields.
        """
        ws = await self._connect()
        while True:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                return
            except websockets.exceptions.ConnectionClosed:
                return
            yield _decode_frame(data)

    def collect(self, count: int, timeout: float = 10.0) -> list[dict]:
        """Synchronously collect up to *count* events (or until *timeout*).

        Bridges async-to-sync via ``asyncio.run()``.  Suitable for
        standard (non-async) pytest tests.
        """
        _check_deps()

        async def _collect() -> list[dict]:
            results: list[dict] = []
            async for event in self.events(timeout=timeout):
                results.append(event)
                if len(results) >= count:
                    break
            # Close the WebSocket opened within this event loop before
            # asyncio.run() destroys the loop.
            if self._ws is not None:
                await self._ws.close()
                self._ws = None
            return results

        return asyncio.run(_collect())

    def close(self) -> None:
        """Close the WebSocket connection if open."""
        if self._ws is not None:
            asyncio.run(self._ws.close())
            self._ws = None

    def __enter__(self) -> FirehoseSubscription:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    async def __aenter__(self) -> FirehoseSubscription:
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
