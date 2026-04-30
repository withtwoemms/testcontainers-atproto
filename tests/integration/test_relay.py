"""Integration tests: RelayContainer with federated PDS instances."""

import time

import pytest

from testcontainers_atproto import PDSContainer, RelayContainer

pytestmark = pytest.mark.requires_docker

_COLLECTION = "app.bsky.feed.post"


def _post_record(text: str = "relay test") -> dict:
    return {
        "$type": _COLLECTION,
        "text": text,
        "createdAt": "2026-01-01T00:00:00Z",
    }


def _record_commits(events: list[dict], did: str | None = None) -> list[dict]:
    """Filter events down to #commit events with non-empty ops."""
    commits = [
        e for e in events
        if e["header"].get("t") == "#commit" and e["body"].get("ops")
    ]
    if did is not None:
        commits = [c for c in commits if c["body"]["repo"] == did]
    return commits


class TestRelayHealth:
    """Relay container starts and responds to health checks."""

    def test_relay_health(self, pds_relay):
        _pds_a, _pds_b, relay = pds_relay
        result = relay.health()
        assert result.get("status") == "ok"

    def test_relay_has_port(self, pds_relay):
        _pds_a, _pds_b, relay = pds_relay
        assert relay.port > 0

    def test_relay_has_base_url(self, pds_relay):
        _pds_a, _pds_b, relay = pds_relay
        assert relay.base_url.startswith("http://")


class TestRelayCrawl:
    """Relay crawls PDS instances and lists known hosts."""

    def test_list_hosts_after_crawl(self, pds_relay):
        pds_a, pds_b, relay = pds_relay
        # Create accounts so each PDS generates events the relay can observe
        pds_a.create_account("rl-host-a.test")
        pds_b.create_account("rl-host-b.test")
        # Give the relay time to process the events
        time.sleep(3)
        hosts = relay.list_hosts()
        hostnames = [h.get("hostname", "") for h in hosts]
        assert any("pds-a" in h for h in hostnames)
        assert any("pds-b" in h for h in hostnames)


class TestRelayFirehose:
    """Relay firehose receives events from crawled PDS instances."""

    def test_relay_firehose_receives_pds_event(self, pds_relay):
        pds_a, _pds_b, relay = pds_relay
        account = pds_a.create_account("rl-event.test")
        account.create_record(_COLLECTION, _post_record("hello via relay"))

        # Allow time for the event to propagate through the relay
        time.sleep(2)

        sub = relay.subscribe()
        events = sub.collect(count=100, timeout=10.0)
        commits = _record_commits(events, did=account.did)
        assert len(commits) >= 1
        assert any(c["body"]["repo"] == account.did for c in commits)

    def test_relay_aggregates_both_pds(self, pds_relay):
        pds_a, pds_b, relay = pds_relay
        alice = pds_a.create_account("rl-agg-a.test")
        bob = pds_b.create_account("rl-agg-b.test")

        alice.create_record(_COLLECTION, _post_record("from PDS-A"))
        bob.create_record(_COLLECTION, _post_record("from PDS-B"))

        # Allow time for events to propagate
        time.sleep(2)

        sub = relay.subscribe()
        events = sub.collect(count=100, timeout=10.0)
        commits = _record_commits(events)

        repos = {c["body"]["repo"] for c in commits}
        assert alice.did in repos
        assert bob.did in repos
