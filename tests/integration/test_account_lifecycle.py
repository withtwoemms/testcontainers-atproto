"""Integration tests: account lifecycle, admin operations, and moderation."""

import re
import time

import httpx
import pytest

from testcontainers_atproto import PDSContainer, XrpcError

pytestmark = pytest.mark.requires_docker


def _extract_token(pds: PDSContainer, message_id: str) -> str:
    """Fetch full message from Mailpit and extract a token."""
    url = pds._mailpit_api_url()
    resp = httpx.get(f"{url}/api/v1/message/{message_id}", timeout=10.0)
    resp.raise_for_status()
    body = resp.json()
    text = body.get("Text", "")
    match = re.search(r"[?&]code=([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"(?:token|code)[=:]\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"^\s*([A-Z0-9]{5}-[A-Z0-9]{5})\s*$", text, re.MULTILINE)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract token from email body:\n{text}")


# --- Deactivate / Activate ---


class TestDeactivateActivate:
    """Account deactivation and reactivation."""

    def test_deactivate_blocks_repo_operations(self, pds_session):
        alice = pds_session.create_account("lc-deact.test")
        alice.deactivate()

        with pytest.raises(XrpcError):
            alice.list_records("app.bsky.feed.post")

    def test_activate_restores_access(self, pds_session):
        alice = pds_session.create_account("lc-activ.test")
        alice.deactivate()
        alice.activate()

        session = pds_session.xrpc_get(
            "com.atproto.server.getSession",
            auth=alice.access_jwt,
        )
        assert session["did"] == alice.did

    def test_deactivate_with_delete_after(self, pds_session):
        alice = pds_session.create_account("lc-delaf.test")
        # Should not raise — deleteAfter is accepted by the PDS
        alice.deactivate(delete_after="2099-01-01T00:00:00Z")
        alice.activate()

    def test_deactivation_does_not_affect_other_accounts(self, pds_session):
        alice = pds_session.create_account("lc-isoa.test")
        bob = pds_session.create_account("lc-isob.test")

        alice.deactivate()

        # Bob is unaffected
        session = pds_session.xrpc_get(
            "com.atproto.server.getSession",
            auth=bob.access_jwt,
        )
        assert session["did"] == bob.did


# --- Check Account Status ---


class TestCheckAccountStatus:
    """Account status queries."""

    def test_active_account_status(self, pds_session):
        alice = pds_session.create_account("lc-stat.test")
        status = alice.check_account_status()
        assert status["activated"] is True
        assert status["validDid"] is True

    def test_status_has_expected_fields(self, pds_session):
        alice = pds_session.create_account("lc-flds.test")
        status = alice.check_account_status()
        expected_fields = [
            "activated",
            "validDid",
            "repoCommit",
            "repoRev",
            "repoBlocks",
            "indexedRecords",
            "privateStateValues",
            "expectedBlobs",
            "importedBlobs",
        ]
        for field in expected_fields:
            assert field in status, f"Missing field: {field}"


# --- Delete Account ---


class TestDeleteAccount:
    """Account deletion (requires email_mode='capture')."""

    def test_full_delete_flow(self, pds_email_session):
        alice = pds_email_session.create_account(
            "lc-del.test",
            password="test-password",
        )

        # Confirm email first (required for account deletion)
        alice.request_email_confirmation()
        confirm_msg = pds_email_session.await_email(alice.email)
        confirm_token = _extract_token(pds_email_session, confirm_msg["ID"])
        alice.confirm_email(confirm_token)

        # Request account deletion
        alice.request_account_delete()

        # Wait for deletion email
        time.sleep(1.0)
        messages = pds_email_session.mailbox(alice.email)
        delete_msg = messages[0]
        delete_token = _extract_token(pds_email_session, delete_msg["ID"])

        # Delete the account
        alice.delete_account("test-password", delete_token)

        # Verify account is gone — session should fail
        with pytest.raises(XrpcError):
            pds_email_session.xrpc_get(
                "com.atproto.server.getSession",
                auth=alice.access_jwt,
            )


# --- Admin Primitives ---


class TestAdminPrimitives:
    """Raw admin_get and admin_post methods."""

    def test_admin_get_returns_dict(self, pds_session):
        alice = pds_session.create_account("lc-admg.test")
        result = pds_session.admin_get(
            "com.atproto.admin.getSubjectStatus",
            params={"did": alice.did},
        )
        assert isinstance(result, dict)
        assert "subject" in result

    def test_admin_get_raises_for_unknown_method(self, pds_session):
        with pytest.raises(XrpcError):
            pds_session.admin_get("com.atproto.admin.nonExistentMethod")

    def test_admin_post_creates_invite_code(self, pds_session):
        result = pds_session.admin_post(
            "com.atproto.server.createInviteCode",
            data={"useCount": 1},
        )
        assert "code" in result


# --- Takedown / Restore ---


class TestTakedownRestore:
    """Admin takedown and restore operations."""

    def test_takedown_blocks_access(self, pds_session):
        alice = pds_session.create_account("lc-tkdn.test")
        pds_session.takedown(alice)

        with pytest.raises(XrpcError):
            pds_session.xrpc_get(
                "com.atproto.server.getSession",
                auth=alice.access_jwt,
            )

    def test_restore_unblocks_access(self, pds_session):
        alice = pds_session.create_account("lc-rstr.test")
        pds_session.takedown(alice)
        pds_session.restore(alice)

        session = pds_session.xrpc_get(
            "com.atproto.server.getSession",
            auth=alice.access_jwt,
        )
        assert session["did"] == alice.did

    def test_takedown_returns_subject(self, pds_session):
        alice = pds_session.create_account("lc-tksb.test")
        result = pds_session.takedown(alice)
        assert "subject" in result

    def test_takedown_does_not_affect_other_accounts(self, pds_session):
        alice = pds_session.create_account("lc-tkia.test")
        bob = pds_session.create_account("lc-tkib.test")

        pds_session.takedown(alice)

        session = pds_session.xrpc_get(
            "com.atproto.server.getSession",
            auth=bob.access_jwt,
        )
        assert session["did"] == bob.did


# --- Subject Status ---


class TestSubjectStatus:
    """Admin subject status queries."""

    def test_active_account_has_subject(self, pds_session):
        alice = pds_session.create_account("lc-sact.test")
        status = pds_session.get_subject_status(alice)
        assert "subject" in status

    def test_takedown_status_applied(self, pds_session):
        alice = pds_session.create_account("lc-stka.test")
        pds_session.takedown(alice)
        status = pds_session.get_subject_status(alice)
        assert status["takedown"]["applied"] is True

    def test_restore_status_not_applied(self, pds_session):
        alice = pds_session.create_account("lc-srst.test")
        pds_session.takedown(alice)
        pds_session.restore(alice)
        status = pds_session.get_subject_status(alice)
        assert status["takedown"]["applied"] is not True


# --- Invite Code Management ---


class TestInviteCodeManagement:
    """Admin invite code operations."""

    def test_disable_invite_codes_by_account(self, pds_session):
        alice = pds_session.create_account("lc-inv.test")
        # Should not raise
        pds_session.disable_invite_codes(accounts=[alice.did])

    def test_disable_invite_codes_empty(self, pds_session):
        # Should not raise
        pds_session.disable_invite_codes(codes=[], accounts=[])


# --- Round-Trip Tests ---


class TestRoundTrips:
    """State preservation across lifecycle transitions."""

    def test_deactivate_activate_preserves_records(self, pds_session):
        alice = pds_session.create_account("lc-rtda.test")
        ref = alice.create_record("app.bsky.feed.post", {
            "$type": "app.bsky.feed.post",
            "text": "survives deactivation",
            "createdAt": "2026-01-01T00:00:00Z",
        })

        alice.deactivate()
        alice.activate()

        record = alice.get_record("app.bsky.feed.post", ref.rkey)
        assert record["text"] == "survives deactivation"

    def test_takedown_restore_preserves_records(self, pds_session):
        alice = pds_session.create_account("lc-rttr.test")
        ref = alice.create_record("app.bsky.feed.post", {
            "$type": "app.bsky.feed.post",
            "text": "survives takedown",
            "createdAt": "2026-01-01T00:00:00Z",
        })

        pds_session.takedown(alice)
        pds_session.restore(alice)

        record = alice.get_record("app.bsky.feed.post", ref.rkey)
        assert record["text"] == "survives takedown"
