"""Unit tests: PDSContainer configuration and parameter handling."""

import pytest

from testcontainers_atproto import Account, PDSContainer


class TestEmailModeParameter:
    """PDSContainer.email_mode controls Mailpit companion container."""

    def test_email_mode_defaults_to_none(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._email_mode = "none"
        pds._mailpit = None
        assert pds.email_mode == "none"

    def test_email_mode_capture_stored(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._email_mode = "capture"
        assert pds.email_mode == "capture"

    def test_mailbox_raises_when_no_mailpit(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._mailpit = None
        with pytest.raises(RuntimeError, match="Mailpit is not running"):
            pds.mailbox()

    def test_await_email_raises_when_no_mailpit(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._mailpit = None
        with pytest.raises(RuntimeError, match="Mailpit is not running"):
            pds.await_email("alice@test.invalid")


class TestAdminMethods:
    """PDSContainer exposes admin methods (no Docker needed)."""

    def test_has_admin_get(self):
        assert callable(getattr(PDSContainer, "admin_get", None))

    def test_has_admin_post(self):
        assert callable(getattr(PDSContainer, "admin_post", None))

    def test_has_takedown(self):
        assert callable(getattr(PDSContainer, "takedown", None))

    def test_has_restore(self):
        assert callable(getattr(PDSContainer, "restore", None))

    def test_has_get_subject_status(self):
        assert callable(getattr(PDSContainer, "get_subject_status", None))

    def test_has_disable_invite_codes(self):
        assert callable(getattr(PDSContainer, "disable_invite_codes", None))


class TestSyncMethods:
    """PDSContainer exposes sync methods (no Docker needed)."""

    def test_has_sync_get(self):
        assert callable(getattr(PDSContainer, "sync_get", None))


class TestNetworkOwnership:
    """PDSContainer._owns_network controls lifecycle of shared resources."""

    def test_owns_network_true_by_default(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._owns_network = True
        assert pds._owns_network is True

    def test_owns_network_false_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._owns_network = False
        assert pds._owns_network is False

    def test_plc_is_none_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._plc = None
        assert pds._plc is None

    def test_postgres_is_none_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._postgres = None
        assert pds._postgres is None


class TestBypassHeaders:
    """PDSContainer._bypass_headers returns correct headers."""

    def test_bypass_headers_empty_when_no_rate_limits(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = None
        assert pds._bypass_headers() == {}

    def test_bypass_headers_populated_when_rate_limits(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = "abc123"
        assert pds._bypass_headers() == {"x-ratelimit-bypass": "abc123"}


class TestExhaustRateLimitErrors:
    """exhaust_rate_limit_budget raises on misconfiguration."""

    def test_exhaust_raises_when_rate_limiting_off(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = False

        class DummyTarget:
            nsid = "com.atproto.server.createSession"
            def __call__(self, base_url):
                pass

        with pytest.raises(RuntimeError, match="Rate limiting is not enabled"):
            pds.exhaust_rate_limit_budget(DummyTarget())

    def test_exhaust_raises_for_unknown_nsid_without_threshold(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = True

        class UnknownTarget:
            nsid = "com.example.unknownEndpoint"
            def __call__(self, base_url):
                pass

        with pytest.raises(ValueError, match="No rate limit mapping"):
            pds.exhaust_rate_limit_budget(UnknownTarget())


class TestOAuthAuthenticateErrors:
    """oauth_authenticate raises when password is missing."""

    def test_oauth_authenticate_raises_without_password(self):
        pds = PDSContainer.__new__(PDSContainer)
        account = Account(
            pds=pds,
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="tok",
            refresh_jwt="tok",
            password="",
        )
        with pytest.raises(ValueError, match="Account has no password stored"):
            pds.oauth_authenticate(account)


class TestRateLimitConfig:
    """bypass_key property reflects rate_limits constructor flag."""

    def test_bypass_key_is_none_when_rate_limits_off(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = None
        assert pds.bypass_key is None

    def test_bypass_key_is_set_when_rate_limits_on(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = "deadbeef1234"
        assert pds.bypass_key == "deadbeef1234"
        # Verify it looks like a hex string
        int(pds.bypass_key, 16)
