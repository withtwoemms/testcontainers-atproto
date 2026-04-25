"""Unit tests for OAuth DPoP primitives (no Docker needed)."""

import base64
import hashlib
import json

import pytest

from testcontainers_atproto.oauth import (
    DPoPKey,
    OAuthTokens,
    PKCEChallenge,
    _base64url,
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
