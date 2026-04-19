"""Unit tests: Account property accessors and edge cases."""

import pytest

from testcontainers_atproto import Account


class TestAccountProperties:
    """Account exposes did, handle, access_jwt, and refresh_jwt."""

    def _make_account(self, **overrides) -> Account:
        defaults = dict(
            pds=None,  # type: ignore[arg-type]
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="eyJ.access.token",
            refresh_jwt="eyJ.refresh.token",
        )
        defaults.update(overrides)
        return Account(**defaults)  # type: ignore[arg-type]

    def test_did(self):
        assert self._make_account().did == "did:plc:abc123"

    def test_handle(self):
        assert self._make_account().handle == "alice.test"

    def test_access_jwt(self):
        assert self._make_account().access_jwt == "eyJ.access.token"

    def test_refresh_jwt(self):
        assert self._make_account().refresh_jwt == "eyJ.refresh.token"

    def test_email(self):
        account = self._make_account(email="alice@test.invalid")
        assert account.email == "alice@test.invalid"

    def test_email_defaults_to_empty_string(self):
        account = self._make_account()
        assert account.email == ""

    def test_properties_are_readonly(self):
        account = self._make_account()
        for attr in ("did", "handle", "access_jwt", "refresh_jwt", "email"):
            with pytest.raises(AttributeError):
                setattr(account, attr, "overwritten")

    def test_empty_strings_are_preserved(self):
        account = self._make_account(access_jwt="", refresh_jwt="")
        assert account.access_jwt == ""
        assert account.refresh_jwt == ""

    def test_unicode_handle(self):
        account = self._make_account(handle="t\u00e9st.test")
        assert account.handle == "t\u00e9st.test"


class TestAccountLifecycleMethods:
    """Account exposes lifecycle methods (no Docker needed)."""

    def _make_account(self) -> Account:
        return Account(
            pds=None,  # type: ignore[arg-type]
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="eyJ.access.token",
            refresh_jwt="eyJ.refresh.token",
        )

    def test_has_deactivate(self):
        assert callable(getattr(self._make_account(), "deactivate", None))

    def test_has_activate(self):
        assert callable(getattr(self._make_account(), "activate", None))

    def test_has_check_account_status(self):
        assert callable(getattr(self._make_account(), "check_account_status", None))

    def test_has_request_account_delete(self):
        assert callable(getattr(self._make_account(), "request_account_delete", None))

    def test_has_delete_account(self):
        assert callable(getattr(self._make_account(), "delete_account", None))
