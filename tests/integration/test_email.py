"""Integration tests: email verification and password reset flows."""

import re

import httpx
import pytest

from testcontainers_atproto import PDSContainer

pytestmark = pytest.mark.requires_docker


def _extract_token(pds: PDSContainer, message_id: str) -> str:
    """Fetch full message from Mailpit and extract the verification token.

    The PDS embeds tokens in email bodies as a code (e.g. ``GOKXN-DIGVF``)
    in a URL query parameter ``?code=...`` and on a standalone line.
    """
    url = pds._mailpit_api_url()
    resp = httpx.get(f"{url}/api/v1/message/{message_id}", timeout=10.0)
    resp.raise_for_status()
    body = resp.json()
    text = body.get("Text", "")
    # Look for ?code=XXXXX-XXXXX in a URL
    match = re.search(r"[?&]code=([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    # Fallback: look for token= or code= patterns
    match = re.search(r"(?:token|code)[=:]\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback: standalone code on its own line (e.g. "P5LJR-PVMVR")
    match = re.search(r"^\s*([A-Z0-9]{5}-[A-Z0-9]{5})\s*$", text, re.MULTILINE)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract token from email body:\n{text}")


class TestEmailCaptureMode:
    """PDSContainer with email_mode='capture' boots with Mailpit."""

    def test_container_boots_with_capture_mode(self):
        with PDSContainer(email_mode="capture") as pds:
            assert pds.email_mode == "capture"
            health = pds.health()
            assert "version" in health

    def test_create_account_in_capture_mode(self):
        with PDSContainer(email_mode="capture") as pds:
            account = pds.create_account("alice.test")
            assert account.did.startswith("did:plc:")
            assert account.email == "alice-test@test.invalid"

    def test_mailbox_empty_initially(self):
        with PDSContainer(email_mode="capture") as pds:
            messages = pds.mailbox()
            assert messages == []

    def test_await_email_timeout(self):
        with PDSContainer(email_mode="capture") as pds:
            with pytest.raises(TimeoutError, match="No email"):
                pds.await_email("nobody@test.invalid", timeout=1.0)


class TestEmailVerificationFlow:
    """Full email verification flow against a live PDS."""

    def test_request_and_confirm_email(self):
        with PDSContainer(email_mode="capture") as pds:
            alice = pds.create_account("alice.test")
            email_addr = alice.email

            # Request verification email
            alice.request_email_confirmation()

            # Wait for the email to arrive
            message = pds.await_email(email_addr)
            assert message is not None

            # Extract token and confirm
            token = _extract_token(pds, message["ID"])
            alice.confirm_email(token)

            # Verify the email is now confirmed via session info
            session = pds.xrpc_get(
                "com.atproto.server.getSession",
                auth=alice.access_jwt,
            )
            assert session.get("emailConfirmed") is True

    def test_mailbox_filtered_by_address(self):
        with PDSContainer(email_mode="capture") as pds:
            alice = pds.create_account("alice.test")
            pds.create_account("bob.test")

            alice.request_email_confirmation()
            pds.await_email(alice.email)

            # Filter by alice's address
            alice_messages = pds.mailbox(alice.email)
            assert len(alice_messages) >= 1

            # Bob has no messages
            bob_messages = pds.mailbox("bob-test@test.invalid")
            assert len(bob_messages) == 0


class TestPasswordResetFlow:
    """Full password reset flow against a live PDS."""

    def test_request_and_reset_password(self):
        with PDSContainer(email_mode="capture") as pds:
            alice = pds.create_account(
                "alice.test",
                password="original-password",
            )
            email_addr = alice.email

            # First confirm email (required before password reset)
            alice.request_email_confirmation()
            confirm_msg = pds.await_email(email_addr)
            confirm_token = _extract_token(pds, confirm_msg["ID"])
            alice.confirm_email(confirm_token)

            # Request password reset
            alice.request_password_reset()

            # Wait for reset email (second email for this address)
            # Need to wait for a new message after the confirmation one
            import time
            time.sleep(1.0)  # Give PDS a moment to send
            messages = pds.mailbox(email_addr)
            # Find the reset email (should be newer than the confirmation)
            reset_msg = messages[0]  # Most recent first
            reset_token = _extract_token(pds, reset_msg["ID"])

            # Reset password
            alice.reset_password(reset_token, "new-password-123")

            # Login with new password
            resp = pds.xrpc_post(
                "com.atproto.server.createSession",
                data={
                    "identifier": alice.handle,
                    "password": "new-password-123",
                },
            )
            assert resp["did"] == alice.did
