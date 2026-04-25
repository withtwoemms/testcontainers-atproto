"""Unit tests for OAuth DPoP primitives (no Docker needed)."""

import base64
import hashlib
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from testcontainers_atproto.oauth import (
    DPoPKey,
    OAuthClient,
    OAuthTokens,
    PKCEChallenge,
    _base64url,
    _check_deps,
    _dpop_aware_post,
    _rewrite_url,
)


class TestPKCEChallenge:
    """PKCEChallenge generates valid S256 verifier/challenge pairs."""

    def test_generate_returns_pkce_challenge(self):
        pkce = PKCEChallenge.generate()
        assert isinstance(pkce, PKCEChallenge)
        assert isinstance(pkce.verifier, str)
        assert isinstance(pkce.challenge, str)

    def test_challenge_is_sha256_of_verifier(self):
        pkce = PKCEChallenge.generate()
        expected = _base64url(hashlib.sha256(pkce.verifier.encode()).digest())
        assert pkce.challenge == expected

    def test_each_call_generates_unique_pair(self):
        a = PKCEChallenge.generate()
        b = PKCEChallenge.generate()
        assert a.verifier != b.verifier
        assert a.challenge != b.challenge

    def test_frozen(self):
        pkce = PKCEChallenge.generate()
        with pytest.raises(AttributeError):
            pkce.verifier = "changed"  # type: ignore[misc]


class TestDPoPKey:
    """DPoPKey generates ES256 keys and valid DPoP proofs."""

    def test_generate(self):
        key = DPoPKey.generate()
        assert isinstance(key, DPoPKey)

    def test_public_jwk_has_required_fields(self):
        key = DPoPKey.generate()
        jwk = key.public_jwk
        assert jwk["kty"] == "EC"
        assert jwk["crv"] == "P-256"
        assert "x" in jwk
        assert "y" in jwk

    def test_public_jwk_returns_copy(self):
        key = DPoPKey.generate()
        a = key.public_jwk
        b = key.public_jwk
        assert a == b
        assert a is not b

    def test_proof_is_jwt(self):
        key = DPoPKey.generate()
        proof = key.proof("POST", "http://localhost:3000/oauth/par")
        # JWT has three base64url-encoded segments
        parts = proof.split(".")
        assert len(parts) == 3

    def test_proof_header(self):
        key = DPoPKey.generate()
        proof = key.proof("POST", "http://localhost:3000/oauth/par")
        header_b64 = proof.split(".")[0]
        # Add padding
        header_b64 += "=" * (4 - len(header_b64) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        assert header["typ"] == "dpop+jwt"
        assert header["alg"] == "ES256"
        assert header["jwk"]["kty"] == "EC"

    def test_proof_payload(self):
        key = DPoPKey.generate()
        proof = key.proof("GET", "http://localhost:3000/xrpc/test")
        payload_b64 = proof.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload["htm"] == "GET"
        assert payload["htu"] == "http://localhost:3000/xrpc/test"
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_proof_with_nonce(self):
        key = DPoPKey.generate()
        proof = key.proof("POST", "http://example.com", nonce="test-nonce")
        payload_b64 = proof.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload["nonce"] == "test-nonce"

    def test_proof_with_ath(self):
        key = DPoPKey.generate()
        proof = key.proof("GET", "http://example.com", ath="token-hash")
        payload_b64 = proof.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload["ath"] == "token-hash"

    def test_access_token_hash(self):
        token = "test-access-token"
        ath = DPoPKey.access_token_hash(token)
        expected = _base64url(hashlib.sha256(token.encode()).digest())
        assert ath == expected


class TestOAuthTokens:
    """OAuthTokens parses token endpoint responses."""

    SAMPLE = {
        "access_token": "eyJ.access",
        "token_type": "DPoP",
        "refresh_token": "ref-abc123",
        "scope": "atproto",
        "expires_in": 3600,
        "sub": "did:plc:abc123",
    }

    def test_from_response(self):
        tokens = OAuthTokens.from_response(self.SAMPLE)
        assert tokens.access_token == "eyJ.access"
        assert tokens.token_type == "DPoP"
        assert tokens.refresh_token == "ref-abc123"
        assert tokens.scope == "atproto"
        assert tokens.expires_in == 3600
        assert tokens.sub == "did:plc:abc123"

    def test_frozen(self):
        tokens = OAuthTokens.from_response(self.SAMPLE)
        with pytest.raises(AttributeError):
            tokens.access_token = "changed"  # type: ignore[misc]

    def test_missing_field_raises(self):
        incomplete = {"access_token": "x", "token_type": "DPoP"}
        with pytest.raises(KeyError):
            OAuthTokens.from_response(incomplete)


class TestRewriteUrl:
    """_rewrite_url translates internal PDS URLs to external mapped URLs."""

    def test_basic_rewrite(self):
        result = _rewrite_url(
            "http://localhost:3000/oauth/par",
            "http://localhost:54321",
        )
        assert result == "http://localhost:54321/oauth/par"

    def test_preserves_path_and_query(self):
        result = _rewrite_url(
            "http://localhost:3000/oauth/token?foo=bar",
            "http://localhost:54321",
        )
        assert result == "http://localhost:54321/oauth/token?foo=bar"


class TestRewriteUrlEdgeCases:
    """Edge cases for _rewrite_url."""

    def test_rewrite_preserves_fragment(self):
        result = _rewrite_url(
            "http://localhost:3000/path#frag",
            "http://localhost:54321",
        )
        assert result == "http://localhost:54321/path#frag"

    def test_rewrite_no_port_in_base(self):
        """When base_url has no explicit port, urlparse.port is None."""
        result = _rewrite_url(
            "http://localhost:3000/path",
            "http://example.com:8080",
        )
        assert result == "http://example.com:8080/path"


class TestCheckDeps:
    """_check_deps raises ImportError only when deps are missing."""

    def test_check_deps_does_not_raise_when_installed(self):
        # cryptography and PyJWT are installed in the test env
        _check_deps()  # should not raise


class TestDPoPAwarePost:
    """_dpop_aware_post handles nonce retry logic."""

    def test_dpop_aware_post_retries_on_nonce(self):
        dpop_key = DPoPKey.generate()
        call_count = 0

        def handler(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    400,
                    json={"error": "use_dpop_nonce"},
                    headers={"dpop-nonce": "server-nonce-42"},
                )
            return httpx.Response(200, json={"ok": True})

        with patch("testcontainers_atproto.oauth.httpx.post", side_effect=handler):
            resp, nonce = _dpop_aware_post(
                "http://pds.test/oauth/token",
                dpop_key,
                "http://pds.test/oauth/token",
                None,
                data={"grant_type": "authorization_code"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert nonce == "server-nonce-42"
        assert call_count == 2

    def test_dpop_aware_post_no_retry_on_other_errors(self):
        dpop_key = DPoPKey.generate()

        def handler(*args, **kwargs):
            return httpx.Response(
                400,
                json={"error": "invalid_grant"},
                headers={},
            )

        with patch("testcontainers_atproto.oauth.httpx.post", side_effect=handler):
            resp, nonce = _dpop_aware_post(
                "http://pds.test/oauth/token",
                dpop_key,
                "http://pds.test/oauth/token",
                None,
                data={"grant_type": "authorization_code"},
            )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"

    def test_dpop_aware_post_captures_nonce_from_header(self):
        dpop_key = DPoPKey.generate()

        def handler(*args, **kwargs):
            return httpx.Response(
                200,
                json={"ok": True},
                headers={"dpop-nonce": "fresh-nonce"},
            )

        with patch("testcontainers_atproto.oauth.httpx.post", side_effect=handler):
            resp, nonce = _dpop_aware_post(
                "http://pds.test/oauth/token",
                dpop_key,
                "http://pds.test/oauth/token",
                None,
                data={},
            )
        assert nonce == "fresh-nonce"


class TestOAuthClientInit:
    """OAuthClient constructor sets expected defaults."""

    def _make_client(self, **kwargs):
        defaults = {
            "base_url": "http://localhost:54321",
            "dpop_key": DPoPKey.generate(),
        }
        defaults.update(kwargs)
        return OAuthClient(**defaults)

    def test_default_client_id(self):
        client = self._make_client()
        assert "http://localhost" in client._client_id
        assert "redirect_uri" in client._client_id

    def test_custom_client_id(self):
        client = self._make_client(client_id="http://my-app.test/client")
        assert client._client_id == "http://my-app.test/client"

    def test_default_scope(self):
        client = self._make_client()
        assert client._scope == "atproto transition:generic"

    def test_custom_scope(self):
        client = self._make_client(scope="atproto")
        assert client._scope == "atproto"

    def test_metadata_starts_none(self):
        client = self._make_client()
        assert client._metadata is None


class TestOAuthClientXrpc:
    """OAuthClient.xrpc_get / xrpc_post construct URLs and handle empty bodies."""

    def _make_client(self):
        dpop_key = DPoPKey.generate()
        client = OAuthClient(
            base_url="http://localhost:54321",
            dpop_key=dpop_key,
        )
        # Pre-set metadata to avoid discover() call
        client._metadata = {
            "issuer": "http://localhost:3000",
            "pushed_authorization_request_endpoint": "http://localhost:3000/oauth/par",
            "authorization_endpoint": "http://localhost:3000/oauth/authorize",
            "token_endpoint": "http://localhost:3000/oauth/token",
            "revocation_endpoint": "http://localhost:3000/oauth/revoke",
        }
        return client

    def test_xrpc_get_constructs_url_from_issuer(self):
        client = self._make_client()
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.content = b'{"did": "did:plc:abc"}'
        resp_mock.json.return_value = {"did": "did:plc:abc"}
        resp_mock.headers = {}

        with patch.object(client, "dpop_get", return_value=resp_mock) as mock_get:
            result = client.xrpc_get("com.atproto.repo.describeRepo", "tok-123")
            url_arg = mock_get.call_args[0][0]
            assert url_arg == "http://localhost:3000/xrpc/com.atproto.repo.describeRepo"
        assert result == {"did": "did:plc:abc"}

    def test_xrpc_post_constructs_url_from_issuer(self):
        client = self._make_client()
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.content = b'{"uri": "at://x/y/z", "cid": "bafy"}'
        resp_mock.json.return_value = {"uri": "at://x/y/z", "cid": "bafy"}
        resp_mock.headers = {}

        with patch.object(client, "dpop_post", return_value=resp_mock) as mock_post:
            result = client.xrpc_post("com.atproto.repo.createRecord", "tok-123", data={"text": "hi"})
            url_arg = mock_post.call_args[0][0]
            assert url_arg == "http://localhost:3000/xrpc/com.atproto.repo.createRecord"
        assert result == {"uri": "at://x/y/z", "cid": "bafy"}

    def test_xrpc_get_returns_empty_dict_for_no_content(self):
        client = self._make_client()
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.content = b""
        resp_mock.headers = {}

        with patch.object(client, "dpop_get", return_value=resp_mock):
            result = client.xrpc_get("com.atproto.server.requestEmailConfirmation", "tok-123")
        assert result == {}

    def test_xrpc_post_returns_empty_dict_for_no_content(self):
        client = self._make_client()
        resp_mock = MagicMock()
        resp_mock.status_code = 200
        resp_mock.content = b""
        resp_mock.headers = {}

        with patch.object(client, "dpop_post", return_value=resp_mock):
            result = client.xrpc_post("com.atproto.server.requestEmailConfirmation", "tok-123")
        assert result == {}
