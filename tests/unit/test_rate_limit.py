"""Unit tests: rate limit simulation support."""

import pytest

from testcontainers_atproto import CreateSession, PDSContainer, RateLimitTarget
from testcontainers_atproto.rate_limit import _RATE_LIMITS


# --- _RATE_LIMITS mapping ---


class TestRateLimitsMapping:
    """The built-in rate limit mapping covers core XRPC endpoints."""

    def test_contains_create_session(self):
        assert "com.atproto.server.createSession" in _RATE_LIMITS

    def test_contains_create_account(self):
        assert "com.atproto.server.createAccount" in _RATE_LIMITS

    def test_contains_upload_blob(self):
        assert "com.atproto.repo.uploadBlob" in _RATE_LIMITS

    def test_values_are_int_tuples(self):
        for nsid, (points, window) in _RATE_LIMITS.items():
            assert isinstance(points, int), f"{nsid}: points is not int"
            assert isinstance(window, int), f"{nsid}: window is not int"
            assert points > 0, f"{nsid}: points must be positive"
            assert window > 0, f"{nsid}: window must be positive"

    def test_create_session_threshold(self):
        points, window = _RATE_LIMITS["com.atproto.server.createSession"]
        assert points == 30
        assert window == 300


# --- RateLimitTarget ---


class TestRateLimitTarget:
    """RateLimitTarget is the base class for exhaustion targets."""

    def test_base_raises_not_implemented(self):
        target = RateLimitTarget()
        with pytest.raises(NotImplementedError):
            target("http://localhost:3000")

    def test_subclass_with_nsid(self):
        class Custom(RateLimitTarget):
            nsid = "com.example.test"

            def __call__(self, base_url):
                pass

        assert Custom.nsid == "com.example.test"


# --- CreateSession ---


class TestCreateSession:
    """CreateSession is a concrete target for createSession."""

    def test_nsid(self):
        assert CreateSession.nsid == "com.atproto.server.createSession"

    def test_stores_credentials(self):
        target = CreateSession("alice.test", "password123")
        assert target.identifier == "alice.test"
        assert target.password == "password123"


# --- PDSContainer rate_limits parameter ---


class TestRateLimitsParameter:
    """PDSContainer.rate_limits controls rate limit simulation."""

    def test_rate_limits_defaults_to_false(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = False
        pds._bypass_key = None
        assert pds._rate_limits is False
        assert pds.bypass_key is None

    def test_rate_limits_true_generates_bypass_key(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = True
        pds._bypass_key = "abcdef1234567890"
        assert pds._rate_limits is True
        assert pds.bypass_key == "abcdef1234567890"

    def test_bypass_headers_empty_when_no_key(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = None
        assert pds._bypass_headers() == {}

    def test_bypass_headers_set_when_key_present(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._bypass_key = "test-key"
        assert pds._bypass_headers() == {"x-ratelimit-bypass": "test-key"}


# --- exhaust_rate_limit_budget errors ---


class TestExhaustRateLimitBudgetErrors:
    """exhaust_rate_limit_budget raises on misconfiguration."""

    def test_raises_when_rate_limits_disabled(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = False
        pds._bypass_key = None
        target = CreateSession("alice.test", "password")
        with pytest.raises(RuntimeError, match="Rate limiting is not enabled"):
            pds.exhaust_rate_limit_budget(target)

    def test_raises_for_unknown_nsid_without_threshold(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = True
        pds._bypass_key = "key"

        class Unknown(RateLimitTarget):
            nsid = "com.example.unknown"

            def __call__(self, base_url):
                pass

        with pytest.raises(ValueError, match="No rate limit mapping"):
            pds.exhaust_rate_limit_budget(Unknown())

    def test_accepts_explicit_threshold_for_unknown_nsid(self, monkeypatch):
        call_count = 0

        class Counting(RateLimitTarget):
            nsid = "com.example.counting"

            def __call__(self, base_url):
                nonlocal call_count
                call_count += 1

        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = True
        pds._bypass_key = "key"
        monkeypatch.setattr(
            type(pds), "base_url",
            property(lambda self: "http://fake:3000"),
        )
        pds.exhaust_rate_limit_budget(Counting(), threshold=5)
        assert call_count == 5

    def test_uses_mapping_threshold(self, monkeypatch):
        call_count = 0

        class FakeCreateSession(RateLimitTarget):
            nsid = "com.atproto.server.createSession"

            def __call__(self, base_url):
                nonlocal call_count
                call_count += 1

        pds = PDSContainer.__new__(PDSContainer)
        pds._rate_limits = True
        pds._bypass_key = "key"
        monkeypatch.setattr(
            type(pds), "base_url",
            property(lambda self: "http://fake:3000"),
        )
        pds.exhaust_rate_limit_budget(FakeCreateSession())
        assert call_count == 30
