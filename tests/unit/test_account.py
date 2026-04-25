"""Unit tests: Account property accessors and edge cases."""

import pytest

from testcontainers_atproto import Account
from testcontainers_atproto.ref import RecordRef


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

    def test_password(self):
        account = self._make_account(password="hunter2")
        assert account.password == "hunter2"

    def test_password_defaults_to_empty_string(self):
        account = self._make_account()
        assert account.password == ""

    def test_properties_are_readonly(self):
        account = self._make_account()
        for attr in ("did", "handle", "access_jwt", "refresh_jwt", "email", "password"):
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


class TestAccountRepoSyncMethods:
    """Account exposes repo sync methods (no Docker needed)."""

    def _make_account(self) -> Account:
        return Account(
            pds=None,  # type: ignore[arg-type]
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="eyJ.access.token",
            refresh_jwt="eyJ.refresh.token",
        )

    def test_has_export_repo(self):
        assert callable(getattr(self._make_account(), "export_repo", None))

    def test_has_get_blob(self):
        assert callable(getattr(self._make_account(), "get_blob", None))


class FakePDS:
    """Records xrpc_post / xrpc_get / sync_get calls for assertion."""

    def __init__(self, response=None):
        self.calls = []
        self._response = response or {}

    def xrpc_post(self, method, data=None, auth=None, **kw):
        self.calls.append(("xrpc_post", method, data, auth, kw))
        return self._response

    def xrpc_get(self, method, params=None, auth=None):
        self.calls.append(("xrpc_get", method, params, auth))
        return self._response

    def sync_get(self, method, params=None, auth=None):
        self.calls.append(("sync_get", method, params, auth))
        return self._response


class TestAccountDelegation:
    """Account methods correctly delegate to PDS with right args and return values."""

    def _make(self, response=None, **overrides):
        pds = FakePDS(response)
        defaults = dict(
            pds=pds,
            did="did:plc:abc123",
            handle="alice.test",
            access_jwt="eyJ.access.token",
            refresh_jwt="eyJ.refresh.token",
            email="alice@test.invalid",
            password="hunter2",
        )
        defaults.update(overrides)
        return Account(**defaults), pds

    # --- Record Operations ---

    def test_create_record_calls_xrpc_post(self):
        acct, pds = self._make(
            response={"uri": "at://did:plc:abc123/app.bsky.feed.post/abc", "cid": "bafy123"}
        )
        ref = acct.create_record("app.bsky.feed.post", {"text": "hello"})
        assert isinstance(ref, RecordRef)
        assert ref.uri == "at://did:plc:abc123/app.bsky.feed.post/abc"
        assert ref.cid == "bafy123"
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.repo.createRecord"
        assert call[2]["repo"] == "did:plc:abc123"
        assert call[2]["collection"] == "app.bsky.feed.post"
        assert call[2]["record"] == {"text": "hello"}
        assert call[2]["validate"] is False
        assert "rkey" not in call[2]
        assert call[3] == "eyJ.access.token"

    def test_create_record_with_rkey(self):
        acct, pds = self._make(
            response={"uri": "at://did:plc:abc123/app.bsky.feed.post/self", "cid": "bafy123"}
        )
        acct.create_record("app.bsky.feed.post", {"text": "hi"}, rkey="self")
        assert pds.calls[0][2]["rkey"] == "self"

    def test_get_record_calls_xrpc_get(self):
        acct, pds = self._make(response={"value": {"text": "hello"}})
        result = acct.get_record("app.bsky.feed.post", "abc")
        assert result == {"text": "hello"}
        call = pds.calls[0]
        assert call[0] == "xrpc_get"
        assert call[1] == "com.atproto.repo.getRecord"
        assert call[2] == {"repo": "did:plc:abc123", "collection": "app.bsky.feed.post", "rkey": "abc"}
        assert call[3] == "eyJ.access.token"

    def test_list_records_calls_xrpc_get(self):
        records = [{"uri": "at://x/y/z", "value": {}}]
        acct, pds = self._make(response={"records": records})
        result = acct.list_records("app.bsky.feed.post", limit=10)
        assert result == records
        call = pds.calls[0]
        assert call[0] == "xrpc_get"
        assert call[1] == "com.atproto.repo.listRecords"
        assert call[2]["limit"] == 10
        assert call[3] == "eyJ.access.token"

    def test_delete_record_calls_xrpc_post(self):
        acct, pds = self._make()
        result = acct.delete_record("app.bsky.feed.post", "abc")
        assert result is None
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.repo.deleteRecord"
        assert call[2] == {"repo": "did:plc:abc123", "collection": "app.bsky.feed.post", "rkey": "abc"}
        assert call[3] == "eyJ.access.token"

    def test_put_record_calls_xrpc_post(self):
        acct, pds = self._make(
            response={"uri": "at://did:plc:abc123/app.bsky.feed.post/abc", "cid": "bafy456"}
        )
        ref = acct.put_record("app.bsky.feed.post", "abc", {"text": "updated"})
        assert isinstance(ref, RecordRef)
        assert ref.cid == "bafy456"
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.repo.putRecord"
        assert call[2]["rkey"] == "abc"
        assert call[2]["record"] == {"text": "updated"}

    def test_upload_blob_calls_xrpc_post(self):
        blob_ref = {"$type": "blob", "ref": {"$link": "bafy789"}}
        acct, pds = self._make(response={"blob": blob_ref})
        result = acct.upload_blob(b"\x89PNG", "image/png")
        assert result == blob_ref
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.repo.uploadBlob"
        assert call[3] == "eyJ.access.token"
        assert call[4]["content"] == b"\x89PNG"
        assert call[4]["content_type"] == "image/png"

    def test_strong_ref_returns_uri_and_cid(self):
        acct, pds = self._make(
            response={"uri": "at://did:plc:abc123/app.bsky.feed.post/abc", "cid": "bafy123"}
        )
        result = acct.strong_ref("app.bsky.feed.post", "abc")
        assert result == {"uri": "at://did:plc:abc123/app.bsky.feed.post/abc", "cid": "bafy123"}
        call = pds.calls[0]
        assert call[0] == "xrpc_get"
        assert call[1] == "com.atproto.repo.getRecord"

    # --- Session ---

    def test_refresh_session_updates_tokens(self):
        acct, pds = self._make(
            response={"accessJwt": "new.access", "refreshJwt": "new.refresh"}
        )
        acct.refresh_session()
        assert acct.access_jwt == "new.access"
        assert acct.refresh_jwt == "new.refresh"
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.refreshSession"
        assert call[3] == "eyJ.refresh.token"

    # --- Email Verification ---

    def test_request_email_confirmation_calls_xrpc_post(self):
        acct, pds = self._make()
        acct.request_email_confirmation()
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.requestEmailConfirmation"
        assert call[3] == "eyJ.access.token"

    def test_confirm_email_passes_email_and_token(self):
        acct, pds = self._make()
        acct.confirm_email("tok-123")
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.confirmEmail"
        assert call[2] == {"email": "alice@test.invalid", "token": "tok-123"}
        assert call[3] == "eyJ.access.token"

    def test_request_password_reset_passes_email(self):
        acct, pds = self._make()
        acct.request_password_reset()
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.requestPasswordReset"
        assert call[2] == {"email": "alice@test.invalid"}
        assert call[3] is None  # no auth

    def test_reset_password_passes_token_and_new_password(self):
        acct, pds = self._make()
        acct.reset_password("tok-456", "new-pass")
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.resetPassword"
        assert call[2] == {"token": "tok-456", "password": "new-pass"}
        assert call[3] is None  # no auth

    # --- Account Lifecycle ---

    def test_deactivate_calls_xrpc_post(self):
        acct, pds = self._make()
        acct.deactivate()
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.deactivateAccount"
        assert call[2] == {}
        assert call[3] == "eyJ.access.token"

    def test_deactivate_with_delete_after(self):
        acct, pds = self._make()
        acct.deactivate(delete_after="2025-01-01T00:00:00Z")
        call = pds.calls[0]
        assert call[2] == {"deleteAfter": "2025-01-01T00:00:00Z"}

    def test_activate_calls_xrpc_post(self):
        acct, pds = self._make()
        acct.activate()
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.activateAccount"
        assert call[3] == "eyJ.access.token"

    def test_check_account_status_calls_xrpc_get(self):
        status = {"activated": True, "validDid": True}
        acct, pds = self._make(response=status)
        result = acct.check_account_status()
        assert result == status
        call = pds.calls[0]
        assert call[0] == "xrpc_get"
        assert call[1] == "com.atproto.server.checkAccountStatus"
        assert call[3] == "eyJ.access.token"

    def test_request_account_delete_calls_xrpc_post(self):
        acct, pds = self._make()
        acct.request_account_delete()
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.requestAccountDelete"
        assert call[3] == "eyJ.access.token"

    def test_delete_account_passes_did_password_token(self):
        acct, pds = self._make()
        acct.delete_account("hunter2", "del-tok-789")
        call = pds.calls[0]
        assert call[0] == "xrpc_post"
        assert call[1] == "com.atproto.server.deleteAccount"
        assert call[2] == {"did": "did:plc:abc123", "password": "hunter2", "token": "del-tok-789"}
        assert call[3] is None  # no auth

    # --- Repo Sync ---

    def test_export_repo_calls_sync_get(self):
        acct, pds = self._make(response=b"\x00CAR")
        result = acct.export_repo()
        assert result == b"\x00CAR"
        call = pds.calls[0]
        assert call[0] == "sync_get"
        assert call[1] == "com.atproto.sync.getRepo"
        assert call[2] == {"did": "did:plc:abc123"}

    def test_get_blob_calls_sync_get(self):
        acct, pds = self._make(response=b"\x89PNG")
        result = acct.get_blob("bafy-blob-cid")
        assert result == b"\x89PNG"
        call = pds.calls[0]
        assert call[0] == "sync_get"
        assert call[1] == "com.atproto.sync.getBlob"
        assert call[2] == {"did": "did:plc:abc123", "cid": "bafy-blob-cid"}
