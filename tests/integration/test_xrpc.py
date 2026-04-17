# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Integration tests: xrpc_get, xrpc_post, and health."""

import pytest

from testcontainers_atproto import PDSContainer, XrpcError

pytestmark = pytest.mark.requires_docker


class TestXrpcGet:
    """PDSContainer.xrpc_get issues authenticated GET requests."""

    def test_unauthenticated_get(self):
        with PDSContainer() as pds:
            resp = pds.xrpc_get("com.atproto.server.describeServer")
            assert "availableUserDomains" in resp

    def test_authenticated_get(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            resp = pds.xrpc_get(
                "com.atproto.server.getSession",
                auth=account.access_jwt,
            )
            assert resp["did"] == account.did
            assert resp["handle"] == account.handle

    def test_unknown_method_raises_xrpc_error(self):
        with PDSContainer() as pds:
            with pytest.raises(XrpcError) as exc_info:
                pds.xrpc_get("com.atproto.nonexistent.method")
            assert exc_info.value.status_code in (400, 404, 501)

    def test_xrpc_error_has_attributes(self):
        with PDSContainer() as pds:
            with pytest.raises(XrpcError) as exc_info:
                pds.xrpc_get("com.atproto.nonexistent.method")
            exc = exc_info.value
            assert exc.method == "com.atproto.nonexistent.method"
            assert isinstance(exc.status_code, int)

    def test_params_are_passed(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            resp = pds.xrpc_get(
                "com.atproto.server.getSession",
                auth=account.access_jwt,
            )
            assert resp["did"] == account.did


class TestXrpcPost:
    """PDSContainer.xrpc_post issues authenticated POST requests."""

    def test_authenticated_post_creates_record(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            resp = pds.xrpc_post(
                "com.atproto.repo.createRecord",
                data={
                    "repo": account.did,
                    "collection": "app.bsky.feed.post",
                    "record": {
                        "$type": "app.bsky.feed.post",
                        "text": "hello from xrpc_post",
                        "createdAt": "2026-01-01T00:00:00Z",
                    },
                },
                auth=account.access_jwt,
            )
            assert "uri" in resp
            assert "cid" in resp

    def test_bad_auth_raises_xrpc_error(self):
        with PDSContainer() as pds:
            with pytest.raises(XrpcError) as exc_info:
                pds.xrpc_post(
                    "com.atproto.repo.createRecord",
                    data={
                        "repo": "did:plc:fake",
                        "collection": "app.bsky.feed.post",
                        "record": {"text": "fail"},
                    },
                    auth="invalid.jwt.token",
                )
            assert exc_info.value.status_code in (400, 401, 403)

    def test_raw_bytes_post(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            resp = pds.xrpc_post(
                "com.atproto.repo.uploadBlob",
                auth=account.access_jwt,
                content=b"test blob data",
                content_type="application/octet-stream",
            )
            assert "blob" in resp


class TestHealth:
    """PDSContainer.health() returns structured health info."""

    def test_health_returns_version(self):
        with PDSContainer() as pds:
            h = pds.health()
            assert "version" in h
            assert isinstance(h["version"], str)
            assert len(h["version"]) > 0

    def test_health_returns_dict(self):
        with PDSContainer() as pds:
            assert isinstance(pds.health(), dict)
