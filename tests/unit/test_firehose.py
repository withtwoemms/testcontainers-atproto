# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Unit tests: FirehoseSubscription construction and guarded imports."""

import cbor2
import pytest

from testcontainers_atproto.firehose import (
    FirehoseSubscription,
    _HAS_FIREHOSE_DEPS,
    _decode_frame,
)


class TestFirehoseSubscriptionConstruction:
    """FirehoseSubscription can be constructed without connecting."""

    def test_stores_ws_url(self):
        sub = FirehoseSubscription(
            "ws://localhost:3000/xrpc/com.atproto.sync.subscribeRepos",
        )
        assert sub._ws_url == "ws://localhost:3000/xrpc/com.atproto.sync.subscribeRepos"

    def test_ws_is_none_initially(self):
        sub = FirehoseSubscription("ws://localhost:3000/xrpc/test")
        assert sub._ws is None


class TestDecodeFrame:
    """_decode_frame correctly parses concatenated CBOR values."""

    def test_decodes_header_and_body(self):
        header = {"op": 1, "t": "#commit"}
        body = {"repo": "did:plc:abc123", "seq": 1, "ops": []}
        data = cbor2.dumps(header) + cbor2.dumps(body)

        result = _decode_frame(data)
        assert result["header"] == header
        assert result["body"]["repo"] == "did:plc:abc123"
        assert result["body"]["seq"] == 1

    def test_preserves_bytes_in_body(self):
        header = {"op": 1, "t": "#commit"}
        body = {"blocks": b"\x00\x01\x02", "seq": 2}
        data = cbor2.dumps(header) + cbor2.dumps(body)

        result = _decode_frame(data)
        assert result["body"]["blocks"] == b"\x00\x01\x02"


class TestGuardedImport:
    """Firehose module is importable and flag reflects installed deps."""

    def test_firehose_module_importable(self):
        assert isinstance(FirehoseSubscription, type)

    def test_has_firehose_deps_flag_is_true(self):
        # Test extras include [all] which pulls in firehose deps.
        assert _HAS_FIREHOSE_DEPS is True


class TestContextManagerProtocol:
    """FirehoseSubscription supports the context manager protocol."""

    def test_enter_returns_self(self):
        sub = FirehoseSubscription("ws://localhost:3000/xrpc/test")
        assert sub.__enter__() is sub

    def test_exit_does_not_raise_when_not_connected(self):
        sub = FirehoseSubscription("ws://localhost:3000/xrpc/test")
        sub.__exit__(None, None, None)  # Should not raise
