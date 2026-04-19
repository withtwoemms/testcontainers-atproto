"""Integration tests: repo sync — export, blob retrieval, and CAR parsing."""

import pytest

from testcontainers_atproto import PDSContainer, XrpcError
from testcontainers_atproto.car import parse_car

pytestmark = pytest.mark.requires_docker

_COLLECTION = "app.bsky.feed.post"


def _post_record(text: str = "sync test") -> dict:
    return {
        "$type": _COLLECTION,
        "text": text,
        "createdAt": "2026-01-01T00:00:00Z",
    }


# --- sync_get ---


class TestSyncGet:
    """PDSContainer.sync_get returns raw bytes from sync endpoints."""

    def test_get_repo_returns_bytes(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            result = pds.sync_get(
                "com.atproto.sync.getRepo",
                params={"did": alice.did},
            )
            assert isinstance(result, bytes)
            assert len(result) > 0

    def test_unknown_method_raises(self):
        with PDSContainer() as pds:
            with pytest.raises(XrpcError):
                pds.sync_get("com.atproto.sync.nonExistent")


# --- Account.export_repo ---


class TestExportRepo:
    """Account.export_repo returns CAR bytes for the account's repo."""

    def test_returns_bytes(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            car_bytes = alice.export_repo()
            assert isinstance(car_bytes, bytes)
            assert len(car_bytes) > 0

    def test_car_bytes_grow_with_records(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            car_before = alice.export_repo()
            for i in range(3):
                alice.create_record(_COLLECTION, _post_record(f"post {i}"))
            car_after = alice.export_repo()
            assert len(car_after) > len(car_before)

    def test_parseable_as_car(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            alice.create_record(_COLLECTION, _post_record("parse me"))
            car_bytes = alice.export_repo()
            car = parse_car(car_bytes)
            assert car.version == 1
            assert len(car.roots) >= 1
            assert len(car.blocks) >= 1

    def test_car_contains_blocks_for_records(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            car_empty = parse_car(alice.export_repo())
            alice.create_record(_COLLECTION, _post_record("new record"))
            car_with_record = parse_car(alice.export_repo())
            assert len(car_with_record.blocks) > len(car_empty.blocks)


# --- Account.get_blob ---


class TestGetBlob:
    """Account.get_blob retrieves uploaded blobs by CID."""

    def test_round_trip_blob(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            original = b"round-trip blob test data"
            blob_ref = alice.upload_blob(original, "application/octet-stream")
            cid = blob_ref["ref"]["$link"]

            retrieved = alice.get_blob(cid)
            assert isinstance(retrieved, bytes)
            assert retrieved == original

    def test_different_blobs_have_different_cids(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            blob1 = alice.upload_blob(b"blob one", "application/octet-stream")
            blob2 = alice.upload_blob(b"blob two", "application/octet-stream")
            assert blob1["ref"]["$link"] != blob2["ref"]["$link"]


# --- Cross-account isolation ---


class TestCrossAccountIsolation:
    """Repo exports are scoped to a single account."""

    def test_separate_repos(self):
        with PDSContainer() as pds:
            alice = pds.create_account("alice.test")
            bob = pds.create_account("bob.test")

            alice.create_record(_COLLECTION, _post_record("alice only"))

            alice_car = parse_car(alice.export_repo())
            bob_car = parse_car(bob.export_repo())

            assert len(alice_car.blocks) > len(bob_car.blocks)
