# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

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


class TestAccountStubs:
    """Unimplemented methods raise NotImplementedError."""

    def _make_account(self) -> Account:
        return Account(
            pds=None,  # type: ignore[arg-type]
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="tok",
            refresh_jwt="tok",
        )

    def test_create_record_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().create_record("app.bsky.feed.post", {})

    def test_get_record_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().get_record("app.bsky.feed.post", "abc")

    def test_list_records_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().list_records("app.bsky.feed.post")

    def test_delete_record_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().delete_record("app.bsky.feed.post", "abc")

    def test_put_record_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().put_record("app.bsky.feed.post", "abc", {})

    def test_upload_blob_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().upload_blob(b"data", "image/png")

    def test_strong_ref_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().strong_ref("app.bsky.feed.post", "abc")

    def test_refresh_session_not_implemented(self):
        with pytest.raises(NotImplementedError):
            self._make_account().refresh_session()
