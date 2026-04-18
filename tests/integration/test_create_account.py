"""Integration tests: Account creation via PDSContainer.create_account."""

import httpx
import pytest

from testcontainers_atproto import Account, PDSContainer, XrpcError

pytestmark = pytest.mark.requires_docker


class TestCreateAccount:
    """create_account returns a valid Account with proper credentials."""

    def test_create_account_returns_account(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert isinstance(account, Account)

    def test_account_has_did(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert account.did.startswith("did:plc:")

    def test_account_has_handle(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert account.handle == "alice.test"

    def test_account_has_jwt_credentials(self):
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert account.access_jwt
            assert account.refresh_jwt

    def test_two_accounts_have_different_dids(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            bob = pds.create_account("bob.test")
            assert alice.did != bob.did

    def test_custom_email_and_password(self):
        with PDSContainer() as pds:
            account = pds.create_account(
                "carol.test",
                email="carol@example.com",
                password="hunter2",
            )
            assert account.did.startswith("did:plc:")

    def test_end_to_end_readme_pattern(self):
        """Validates the exact usage pattern from the README."""
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert pds.base_url.startswith("http://")
            assert account.did.startswith("did:plc:")
            assert account.handle == "alice.test"
            assert account.access_jwt

    def test_access_jwt_is_valid_for_xrpc(self):
        """The returned access_jwt authenticates XRPC calls."""
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            resp = httpx.get(
                f"{pds.base_url}/xrpc/com.atproto.server.getSession",
                headers={"Authorization": f"Bearer {account.access_jwt}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            session = resp.json()
            assert session["did"] == account.did
            assert session["handle"] == account.handle

    def test_multiple_accounts_on_same_pds(self):
        """Three accounts can coexist on a single PDS instance."""
        with PDSContainer() as pds:
            accounts = [
                pds.create_account("alice.test"),
                pds.create_account("bob.test"),
                pds.create_account("carol.test"),
            ]
            dids = {a.did for a in accounts}
            assert len(dids) == 3

    def test_default_email_is_generated(self):
        """When email is omitted, the account is still created successfully."""
        with PDSContainer() as pds:
            account = pds.create_account("alice.test")
            assert account.did.startswith("did:plc:")


class TestCreateAccountRealPLC:
    """Account creation with Postgres-backed PLC directory."""

    def test_create_account_with_real_plc(self):
        with PDSContainer(plc_mode="real") as pds:
            account = pds.create_account("alice.test")
            assert account.did.startswith("did:plc:")
            assert account.handle == "alice.test"
            assert account.access_jwt


class TestCreateAccountAdversarial:
    """Edge cases and error conditions for create_account."""

    def test_duplicate_handle_raises(self):
        """Creating two accounts with the same handle should fail."""
        with PDSContainer() as pds:
            pds.create_account("alice.test")
            with pytest.raises(XrpcError) as exc_info:
                pds.create_account("alice.test")
            assert exc_info.value.status_code == 400

    def test_invalid_handle_domain_raises(self):
        """Handles not ending in .test are rejected by the PDS."""
        with PDSContainer() as pds:
            with pytest.raises(XrpcError):
                pds.create_account("alice.invalid")

    def test_empty_handle_raises(self):
        """An empty handle string is rejected."""
        with PDSContainer() as pds:
            with pytest.raises(XrpcError):
                pds.create_account("")

    def test_duplicate_email_raises(self):
        """Two accounts with the same email should fail."""
        with PDSContainer() as pds:
            pds.create_account("alice.test", email="shared@test.invalid")
            with pytest.raises(XrpcError):
                pds.create_account("bob.test", email="shared@test.invalid")
