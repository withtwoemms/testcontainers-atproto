"""Integration tests: OAuth DPoP flow against a real PDS."""

import pytest

from testcontainers_atproto import DPoPKey, OAuthClient, OAuthTokens, PDSContainer, PKCEChallenge

pytestmark = pytest.mark.requires_docker

_COLLECTION = "app.bsky.feed.post"


def _post_record(text: str = "hello via OAuth") -> dict:
    return {
        "$type": _COLLECTION,
        "text": text,
        "createdAt": "2026-01-01T00:00:00Z",
    }


class TestOAuthDiscovery:
    """OAuth metadata discovery works on the PDS."""

    def test_metadata_has_required_fields(self):
        with PDSContainer() as pds:
            client = pds.oauth_client()
            metadata = client.discover()
            assert "issuer" in metadata
            assert "authorization_endpoint" in metadata
            assert "token_endpoint" in metadata
            assert "pushed_authorization_request_endpoint" in metadata


class TestOAuthFullFlow:
    """Full OAuth DPoP flow: PAR → sign-in → consent → token exchange."""

    def test_authenticate_returns_tokens(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client = pds.oauth_client()
            tokens = client.authenticate("alice.test", "hunter2")
            assert isinstance(tokens, OAuthTokens)
            assert tokens.token_type == "DPoP"
            assert tokens.sub == account.did
            assert tokens.scope == "atproto transition:generic"
            assert len(tokens.access_token) > 0
            assert len(tokens.refresh_token) > 0

    def test_convenience_method(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)
            assert isinstance(tokens, OAuthTokens)
            assert tokens.sub == account.did

    def test_step_by_step_flow(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            dpop_key = DPoPKey.generate()
            client = pds.oauth_client(dpop_key=dpop_key)

            pkce = PKCEChallenge.generate()
            request_uri = client.pushed_authorization_request(
                pkce, state="test-state", login_hint="alice.test",
            )
            assert request_uri.startswith("urn:ietf:params:oauth:request_uri:")

            code = client.authorize(request_uri, "alice.test", "hunter2")
            assert code.startswith("cod-")

            tokens = client.token_exchange(code, pkce)
            assert tokens.token_type == "DPoP"
            assert tokens.sub == account.did


class TestDPoPAuthenticatedRequests:
    """DPoP-authenticated XRPC calls work with OAuth tokens."""

    def test_xrpc_get(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)
            resp = client.xrpc_get(
                "com.atproto.repo.describeRepo",
                tokens.access_token,
                params={"repo": account.did},
            )
            assert resp["handle"] == "alice.test"
            assert resp["did"] == account.did

    def test_xrpc_post_create_record(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)
            resp = client.xrpc_post(
                "com.atproto.repo.createRecord",
                tokens.access_token,
                data={
                    "repo": account.did,
                    "collection": _COLLECTION,
                    "record": _post_record(),
                },
            )
            assert "uri" in resp
            assert "cid" in resp
            assert _COLLECTION in resp["uri"]


class TestTokenRefresh:
    """Token refresh via DPoP works."""

    def test_refresh_returns_new_tokens(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)

            new_tokens = client.refresh_tokens(tokens.refresh_token)
            assert isinstance(new_tokens, OAuthTokens)
            assert new_tokens.sub == account.did
            assert new_tokens.access_token != tokens.access_token

    def test_refreshed_token_works(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)

            new_tokens = client.refresh_tokens(tokens.refresh_token)
            resp = client.xrpc_get(
                "com.atproto.repo.describeRepo",
                new_tokens.access_token,
                params={"repo": account.did},
            )
            assert resp["did"] == account.did


class TestTokenRevocation:
    """Token revocation works."""

    def test_revoke_does_not_raise(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test", password="hunter2")
            client, tokens = pds.oauth_authenticate(account)
            # Should not raise
            client.revoke_token(tokens.access_token)
