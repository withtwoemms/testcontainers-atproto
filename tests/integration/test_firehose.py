"""Integration tests: FirehoseSubscription end-to-end."""

import pytest

from testcontainers_atproto import PDSContainer
from testcontainers_atproto.firehose import FirehoseSubscription

pytestmark = pytest.mark.requires_docker

_COLLECTION = "app.bsky.feed.post"


def _post_record(text: str = "firehose test") -> dict:
    return {
        "$type": _COLLECTION,
        "text": text,
        "createdAt": "2026-01-01T00:00:00Z",
    }


def _record_commits(events: list[dict]) -> list[dict]:
    """Filter events down to #commit events that have non-empty ops.

    The PDS emits several event types (``#identity``, ``#account``,
    ``#sync``) plus an initial ``#commit`` with empty ops for account
    creation.  This helper extracts only the record-operation commits.
    """
    return [
        e for e in events
        if e["header"].get("t") == "#commit" and e["body"].get("ops")
    ]


class TestSubscribeFactory:
    """PDSContainer.subscribe() returns a FirehoseSubscription."""

    def test_returns_firehose_subscription(self):
        with PDSContainer() as pds:
            sub = pds.subscribe()
            assert isinstance(sub, FirehoseSubscription)

    def test_cursor_in_ws_url(self):
        with PDSContainer() as pds:
            sub = pds.subscribe(cursor=42)
            assert "cursor=42" in sub._ws_url

    def test_default_cursor_is_zero(self):
        with PDSContainer() as pds:
            sub = pds.subscribe()
            assert "cursor=0" in sub._ws_url


class TestFirehoseContextManager:
    """FirehoseSubscription works as a context manager."""

    def test_context_manager_enter_exit(self):
        with PDSContainer() as pds:
            sub = pds.subscribe()
            with sub:
                pass  # enter/exit without error


class TestFirehoseCollect:
    """collect() receives events produced by record operations."""

    def test_collect_receives_commit_after_create(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record("hello firehose"))
            sub = pds.subscribe()
            events = sub.collect(count=10, timeout=5.0)

            commits = _record_commits(events)
            assert len(commits) >= 1
            assert commits[0]["body"]["repo"] == account.did

    def test_commit_event_contains_ops(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record())
            sub = pds.subscribe()
            events = sub.collect(count=10, timeout=5.0)

            commits = _record_commits(events)
            assert len(commits) >= 1
            ops = commits[0]["body"]["ops"]
            assert len(ops) >= 1
            assert ops[0]["action"] == "create"
            assert _COLLECTION in ops[0]["path"]

    def test_commit_event_has_seq(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record())
            sub = pds.subscribe()
            events = sub.collect(count=10, timeout=5.0)

            commits = _record_commits(events)
            assert len(commits) >= 1
            assert "seq" in commits[0]["body"]
            assert isinstance(commits[0]["body"]["seq"], int)

    def test_collect_multiple_events(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            for i in range(3):
                account.create_record(_COLLECTION, _post_record(f"post {i}"))
            sub = pds.subscribe()
            events = sub.collect(count=20, timeout=5.0)

            commits = _record_commits(events)
            assert len(commits) >= 3

    def test_collect_timeout_returns_partial(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record())
            sub = pds.subscribe()
            # Request 50 but only ~5 events exist; returns after timeout.
            events = sub.collect(count=50, timeout=3.0)

            assert len(events) >= 1
            assert len(events) < 50

    def test_collect_returns_list_with_no_activity(self):
        with PDSContainer() as pds:
            sub = pds.subscribe()
            events = sub.collect(count=1, timeout=2.0)

            # No accounts created, no events at all — or possibly
            # empty list.  Key assertion: does not hang.
            assert isinstance(events, list)


class TestFirehoseEventStructure:
    """Validate the shape of decoded firehose events."""

    def test_event_has_header_and_body(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record())
            sub = pds.subscribe()
            events = sub.collect(count=10, timeout=5.0)

            assert len(events) >= 1
            assert "header" in events[0]
            assert "body" in events[0]

    def test_header_has_op_field(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            account.create_record(_COLLECTION, _post_record())
            sub = pds.subscribe()
            events = sub.collect(count=10, timeout=5.0)

            assert len(events) >= 1
            assert "op" in events[0]["header"]
