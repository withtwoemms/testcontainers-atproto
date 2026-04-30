"""Integration tests: Account creation via PDSContainer.create_account."""

import httpx
import pytest

from testcontainers_atproto import Account, XrpcError

pytestmark = pytest.mark.requires_docker


class TestCreateAccount:
    """create_account returns a valid Account with proper credentials."""

    def test_create_account_returns_account(self, pds_module):
        account = pds_module.create_account("acct-returns.test")
        assert isinstance(account, Account)

    def test_account_has_did(self, pds_module):
        account = pds_module.create_account("acct-did.test")
        assert account.did.startswith("did:plc:")

    def test_account_has_handle(self, pds_module):
        account = pds_module.create_account("acct-handle.test")
        assert account.handle == "acct-handle.test"

    def test_account_has_jwt_credentials(self, pds_module):
        account = pds_module.create_account("acct-jwt.test")
        assert account.access_jwt
        assert account.refresh_jwt

    def test_two_accounts_have_different_dids(self, pds_module):
        alice = pds_module.create_account("acct-diff-a.test")
        bob = pds_module.create_account("acct-diff-b.test")
        assert alice.did != bob.did

    def test_custom_email_and_password(self, pds_module):
        account = pds_module.create_account(
            "acct-custom.test",
            email="carol@example.com",
            password="hunter2",
        )
        assert account.did.startswith("did:plc:")

    def test_end_to_end_readme_pattern(self, pds_module):
        """Validates the exact usage pattern from the README."""
        account = pds_module.create_account("acct-readme.test")
        assert pds_module.base_url.startswith("http://")
        assert account.did.startswith("did:plc:")
        assert account.handle == "acct-readme.test"
        assert account.access_jwt

    def test_access_jwt_is_valid_for_xrpc(self, pds_module):
        """The returned access_jwt authenticates XRPC calls."""
        account = pds_module.create_account("acct-xrpc.test")
        resp = httpx.get(
            f"{pds_module.base_url}/xrpc/com.atproto.server.getSession",
            headers={"Authorization": f"Bearer {account.access_jwt}"},
            timeout=5.0,
        )
        resp.raise_for_status()
        session = resp.json()
        assert session["did"] == account.did
        assert session["handle"] == account.handle

    def test_multiple_accounts_on_same_pds(self, pds_module):
        """Three accounts can coexist on a single PDS instance."""
        accounts = [
            pds_module.create_account("acct-multi-a.test"),
            pds_module.create_account("acct-multi-b.test"),
            pds_module.create_account("acct-multi-c.test"),
        ]
        dids = {a.did for a in accounts}
        assert len(dids) == 3

    def test_default_email_is_generated(self, pds_module):
        """When email is omitted, the account is still created successfully."""
        account = pds_module.create_account("acct-email.test")
        assert account.did.startswith("did:plc:")


class TestCreateAccountRealPLC:
    """Account creation with Postgres-backed PLC directory."""

    def test_create_account_with_real_plc(self, pds_real_plc_session):
        account = pds_real_plc_session.create_account("plc-acct.test")
        assert account.did.startswith("did:plc:")
        assert account.handle == "plc-acct.test"
        assert account.access_jwt


class TestCreateAccountAdversarial:
    """Edge cases and error conditions for create_account."""

    def test_duplicate_handle_raises(self, pds_module):
        """Creating two accounts with the same handle should fail."""
        pds_module.create_account("adv-dup.test")
        with pytest.raises(XrpcError) as exc_info:
            pds_module.create_account("adv-dup.test")
        assert exc_info.value.status_code == 400

    def test_invalid_handle_domain_raises(self, pds_module):
        """Handles not ending in .test are rejected by the PDS."""
        with pytest.raises(XrpcError):
            pds_module.create_account("adv-bad.invalid")

    def test_empty_handle_raises(self, pds_module):
        """An empty handle string is rejected."""
        with pytest.raises(XrpcError):
            pds_module.create_account("")

    def test_duplicate_email_raises(self, pds_module):
        """Two accounts with the same email should fail."""
        pds_module.create_account("adv-em-a.test", email="adv-shared@test.invalid")
        with pytest.raises(XrpcError):
            pds_module.create_account("adv-em-b.test", email="adv-shared@test.invalid")
