"""Integration tests: Account record operations (CRUD, blobs, session)."""

import pytest

from testcontainers_atproto import RecordRef, XrpcError

pytestmark = pytest.mark.requires_docker

_COLLECTION = "app.bsky.feed.post"


def _post_record(text: str = "hello") -> dict:
    return {
        "$type": _COLLECTION,
        "text": text,
        "createdAt": "2026-01-01T00:00:00Z",
    }


class TestCreateRecord:
    """Account.create_record stores records and returns RecordRef."""

    def test_returns_record_ref(self, pds_module):
        account = pds_module.create_account("rec-cr-ref.test")
        ref = account.create_record(_COLLECTION, _post_record())
        assert isinstance(ref, RecordRef)

    def test_uri_contains_collection(self, pds_module):
        account = pds_module.create_account("rec-cr-uri.test")
        ref = account.create_record(_COLLECTION, _post_record())
        assert _COLLECTION in ref.uri

    def test_cid_is_nonempty(self, pds_module):
        account = pds_module.create_account("rec-cr-cid.test")
        ref = account.create_record(_COLLECTION, _post_record())
        assert len(ref.cid) > 0

    def test_auto_generated_rkey(self, pds_module):
        account = pds_module.create_account("rec-cr-rkey.test")
        ref = account.create_record(_COLLECTION, _post_record())
        assert len(ref.rkey) > 0

    def test_explicit_rkey(self, pds_module):
        account = pds_module.create_account("rec-cr-xrkey.test")
        ref = account.create_record(_COLLECTION, _post_record(), rkey="mykey")
        assert ref.rkey == "mykey"


class TestGetRecord:
    """Account.get_record fetches record values."""

    def test_round_trip(self, pds_module):
        account = pds_module.create_account("rec-get-rt.test")
        record = _post_record("round trip")
        ref = account.create_record(_COLLECTION, record)
        fetched = account.get_record(_COLLECTION, ref.rkey)
        assert fetched["text"] == "round trip"

    def test_nonexistent_raises(self, pds_module):
        account = pds_module.create_account("rec-get-nx.test")
        with pytest.raises(XrpcError):
            account.get_record(_COLLECTION, "nonexistent-rkey")


class TestListRecords:
    """Account.list_records lists collection contents."""

    def test_empty_collection(self, pds_module):
        account = pds_module.create_account("rec-list-empty.test")
        records = account.list_records(_COLLECTION)
        assert records == []

    def test_lists_created_records(self, pds_module):
        account = pds_module.create_account("rec-list-created.test")
        for i in range(3):
            account.create_record(_COLLECTION, _post_record(f"post {i}"))
        records = account.list_records(_COLLECTION)
        assert len(records) == 3

    def test_limit_parameter(self, pds_module):
        account = pds_module.create_account("rec-list-limit.test")
        for i in range(3):
            account.create_record(_COLLECTION, _post_record(f"post {i}"))
        records = account.list_records(_COLLECTION, limit=2)
        assert len(records) == 2


class TestDeleteRecord:
    """Account.delete_record removes records."""

    def test_delete_removes_record(self, pds_module):
        account = pds_module.create_account("rec-del-rm.test")
        ref = account.create_record(_COLLECTION, _post_record())
        account.delete_record(_COLLECTION, ref.rkey)
        with pytest.raises(XrpcError):
            account.get_record(_COLLECTION, ref.rkey)

    def test_delete_returns_none(self, pds_module):
        account = pds_module.create_account("rec-del-ret.test")
        ref = account.create_record(_COLLECTION, _post_record())
        result = account.delete_record(_COLLECTION, ref.rkey)
        assert result is None


class TestPutRecord:
    """Account.put_record creates and updates records.

    Uses a custom collection to allow arbitrary rkeys — Bluesky's
    ``app.bsky.feed.post`` enforces TID-format keys.
    """

    _PUT_COLLECTION = "com.example.test"

    def _put_record_data(self, text: str = "hello") -> dict:
        return {"$type": self._PUT_COLLECTION, "text": text}

    def test_create_via_put(self, pds_module):
        account = pds_module.create_account("rec-put-cr.test")
        ref = account.put_record(
            self._PUT_COLLECTION, "put-key", self._put_record_data("via put"),
        )
        assert isinstance(ref, RecordRef)
        assert ref.rkey == "put-key"

    def test_update_via_put(self, pds_module):
        account = pds_module.create_account("rec-put-up.test")
        account.put_record(self._PUT_COLLECTION, "up-key", self._put_record_data("v1"))
        account.put_record(self._PUT_COLLECTION, "up-key", self._put_record_data("v2"))
        fetched = account.get_record(self._PUT_COLLECTION, "up-key")
        assert fetched["text"] == "v2"

    def test_cid_changes_on_update(self, pds_module):
        account = pds_module.create_account("rec-put-cid.test")
        ref1 = account.put_record(
            self._PUT_COLLECTION, "cid-key", self._put_record_data("v1"),
        )
        ref2 = account.put_record(
            self._PUT_COLLECTION, "cid-key", self._put_record_data("v2"),
        )
        assert ref1.cid != ref2.cid


class TestUploadBlob:
    """Account.upload_blob uploads binary data."""

    def test_upload_returns_blob_dict(self, pds_module):
        account = pds_module.create_account("rec-blob-dict.test")
        blob = account.upload_blob(b"test blob data", "application/octet-stream")
        assert "$type" in blob
        assert blob["$type"] == "blob"

    def test_blob_has_ref(self, pds_module):
        account = pds_module.create_account("rec-blob-ref.test")
        blob = account.upload_blob(b"test data", "application/octet-stream")
        assert "ref" in blob
        assert "$link" in blob["ref"]


class TestStrongRef:
    """Account.strong_ref fetches uri+cid for a record."""

    def test_returns_uri_and_cid(self, pds_module):
        account = pds_module.create_account("rec-sref-uc.test")
        ref = account.create_record(_COLLECTION, _post_record())
        sref = account.strong_ref(_COLLECTION, ref.rkey)
        assert "uri" in sref
        assert "cid" in sref

    def test_matches_create_ref(self, pds_module):
        account = pds_module.create_account("rec-sref-match.test")
        ref = account.create_record(_COLLECTION, _post_record())
        sref = account.strong_ref(_COLLECTION, ref.rkey)
        assert sref["uri"] == ref.uri
        assert sref["cid"] == ref.cid


class TestRefreshSession:
    """Account.refresh_session rotates auth tokens."""

    def test_refresh_succeeds_and_authenticates(self, pds_module):
        """refresh_session completes and the resulting token is valid."""
        account = pds_module.create_account("rec-sess-auth.test")
        account.refresh_session()
        # The refreshed token must authenticate successfully
        resp = pds_module.xrpc_get(
            "com.atproto.server.getSession",
            auth=account.access_jwt,
        )
        assert resp["did"] == account.did

    def test_new_token_works(self, pds_module):
        account = pds_module.create_account("rec-sess-new.test")
        account.refresh_session()
        resp = pds_module.xrpc_get(
            "com.atproto.server.getSession",
            auth=account.access_jwt,
        )
        assert resp["did"] == account.did


class TestEndToEnd:
    """Full CRUD lifecycle on a single PDS."""

    def test_full_crud_lifecycle(self, pds_module):
        account = pds_module.create_account("rec-e2e.test")

        # Create
        ref = account.create_record(_COLLECTION, _post_record("original"))
        assert isinstance(ref, RecordRef)

        # Read
        fetched = account.get_record(_COLLECTION, ref.rkey)
        assert fetched["text"] == "original"

        # Update (via put)
        ref2 = account.put_record(_COLLECTION, ref.rkey, _post_record("updated"))
        assert ref2.cid != ref.cid
        assert account.get_record(_COLLECTION, ref.rkey)["text"] == "updated"

        # List
        records = account.list_records(_COLLECTION)
        assert len(records) == 1

        # Delete
        account.delete_record(_COLLECTION, ref.rkey)
        with pytest.raises(XrpcError):
            account.get_record(_COLLECTION, ref.rkey)

        # Verify empty
        assert account.list_records(_COLLECTION) == []
