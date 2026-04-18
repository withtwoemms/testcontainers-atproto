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

    def test_properties_are_readonly(self):
        account = self._make_account()
        for attr in ("did", "handle", "access_jwt", "refresh_jwt"):
            with pytest.raises(AttributeError):
                setattr(account, attr, "overwritten")

    def test_empty_strings_are_preserved(self):
        account = self._make_account(access_jwt="", refresh_jwt="")
        assert account.access_jwt == ""
        assert account.refresh_jwt == ""

    def test_unicode_handle(self):
        account = self._make_account(handle="t\u00e9st.test")
        assert account.handle == "t\u00e9st.test"
