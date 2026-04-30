"""Unit tests: RelayContainer configuration and parameter handling."""

from testcontainers_atproto import RelayContainer


class TestRelayDefaults:
    """RelayContainer exposes expected defaults."""

    def test_admin_password_generated_when_not_provided(self):
        relay = RelayContainer.__new__(RelayContainer)
        relay._admin_password = "deadbeef1234"
        assert relay.admin_password == "deadbeef1234"
        # Verify it looks like a hex string
        int(relay.admin_password, 16)

    def test_custom_admin_password(self):
        relay = RelayContainer.__new__(RelayContainer)
        relay._admin_password = "my-secret"
        assert relay.admin_password == "my-secret"


class TestRelayMethods:
    """RelayContainer exposes expected methods."""

    def test_has_request_crawl(self):
        assert callable(getattr(RelayContainer, "request_crawl", None))

    def test_has_crawl_pds(self):
        assert callable(getattr(RelayContainer, "crawl_pds", None))

    def test_has_list_hosts(self):
        assert callable(getattr(RelayContainer, "list_hosts", None))

    def test_has_subscribe(self):
        assert callable(getattr(RelayContainer, "subscribe", None))

    def test_has_health(self):
        assert callable(getattr(RelayContainer, "health", None))
