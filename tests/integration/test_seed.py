"""Integration tests: Seed builder and dict-based seeding end-to-end."""

import pytest

from testcontainers_atproto import RecordRef
from testcontainers_atproto.seed import Seed, seed_from_dict
from testcontainers_atproto.world import World

pytestmark = pytest.mark.requires_docker


class TestSeedBuilderApply:
    """End-to-end seed-apply cycle with the fluent builder."""

    def test_single_account_no_records(self, pds_session):
        world = Seed(pds_session).account("sd-single.test").apply()
        assert "sd-single.test" in world.accounts
        assert world.records["sd-single.test"] == []

    def test_single_account_with_posts(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-posts.test")
                .post("first")
                .post("second")
            .apply()
        )
        assert len(world.records["sd-posts.test"]) == 2
        assert all(isinstance(r, RecordRef) for r in world.records["sd-posts.test"])

    def test_multi_account_record_counts(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-multi-a.test")
                .post("Hello from Alice")
                .post("Another post")
            .account("sd-multi-b.test")
                .post("Bob's first post")
            .apply()
        )
        assert len(world.accounts) == 2
        assert len(world.records["sd-multi-a.test"]) == 2
        assert len(world.records["sd-multi-b.test"]) == 1

    def test_follow_creates_graph_record(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-fol-a.test")
            .account("sd-fol-b.test")
                .follow("sd-fol-a.test")
            .apply()
        )
        bob = world.accounts["sd-fol-b.test"]
        alice = world.accounts["sd-fol-a.test"]
        follows = bob.list_records("app.bsky.graph.follow")
        assert len(follows) == 1
        assert follows[0]["value"]["subject"] == alice.did

    def test_like_resolves_cross_account_ref(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-like-a.test")
                .post("likeable post")
            .account("sd-like-b.test")
                .like("sd-like-a.test", 0)
            .apply()
        )
        bob = world.accounts["sd-like-b.test"]
        likes = bob.list_records("app.bsky.feed.like")
        assert len(likes) == 1
        like_subject = likes[0]["value"]["subject"]
        assert like_subject["uri"] == world.records["sd-like-a.test"][0].uri

    def test_repost_resolves_cross_account_ref(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-rp-a.test")
                .post("repostable")
            .account("sd-rp-b.test")
                .repost("sd-rp-a.test", 0)
            .apply()
        )
        bob = world.accounts["sd-rp-b.test"]
        reposts = bob.list_records("app.bsky.feed.repost")
        assert len(reposts) == 1
        repost_subject = reposts[0]["value"]["subject"]
        assert repost_subject["uri"] == world.records["sd-rp-a.test"][0].uri

    def test_custom_collection_record(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-custom.test")
                .record("com.example.test", {
                    "$type": "com.example.test",
                    "value": 42,
                })
            .apply()
        )
        ref = world.records["sd-custom.test"][0]
        assert ref.collection == "com.example.test"

    def test_record_with_explicit_rkey(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-rkey.test")
                .record(
                    "com.example.test",
                    {"$type": "com.example.test", "value": 1},
                    rkey="mykey",
                )
            .apply()
        )
        assert world.records["sd-rkey.test"][0].rkey == "mykey"

    def test_like_out_of_range_raises(self, pds_session):
        builder = (
            Seed(pds_session)
            .account("sd-oor-a.test")
                .post("only post")
            .account("sd-oor-b.test")
                .like("sd-oor-a.test", 99)
        )
        with pytest.raises(IndexError, match="record index 99"):
            builder.apply()

    def test_blob_upload(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-blob.test")
                .blob(b"test blob data", "application/octet-stream")
            .apply()
        )
        assert len(world.blobs["sd-blob.test"]) == 1
        assert world.blobs["sd-blob.test"][0]["$type"] == "blob"

    def test_world_is_instance(self, pds_session):
        world = Seed(pds_session).account("sd-world.test").apply()
        assert isinstance(world, World)


class TestSeedDictApply:
    """End-to-end seed-apply cycle with the dict-based API."""

    def test_pds_seed_method(self, pds_session):
        world = pds_session.seed({"accounts": [{"handle": "sd-dict.test"}]})
        assert isinstance(world, World)
        assert "sd-dict.test" in world.accounts

    def test_dict_with_posts_and_follows(self, pds_session):
        world = seed_from_dict(pds_session, {
            "accounts": [
                {
                    "handle": "sd-dpf-a.test",
                    "posts": ["Hello from Alice"],
                },
                {
                    "handle": "sd-dpf-b.test",
                    "posts": ["Hi from Bob"],
                    "follows": ["sd-dpf-a.test"],
                },
            ],
        })
        assert len(world.records["sd-dpf-a.test"]) == 1
        assert len(world.records["sd-dpf-b.test"]) == 1
        bob = world.accounts["sd-dpf-b.test"]
        follows = bob.list_records("app.bsky.graph.follow")
        assert len(follows) == 1

    def test_dict_with_likes(self, pds_session):
        world = seed_from_dict(pds_session, {
            "accounts": [
                {
                    "handle": "sd-dlk-a.test",
                    "posts": ["Likeable post"],
                },
                {
                    "handle": "sd-dlk-b.test",
                    "likes": [{"handle": "sd-dlk-a.test", "index": 0}],
                },
            ],
        })
        bob = world.accounts["sd-dlk-b.test"]
        likes = bob.list_records("app.bsky.feed.like")
        assert len(likes) == 1

    def test_dict_with_custom_records(self, pds_session):
        world = seed_from_dict(pds_session, {
            "accounts": [
                {
                    "handle": "sd-dcr.test",
                    "records": [
                        {
                            "collection": "com.example.test",
                            "record": {"$type": "com.example.test", "v": 1},
                        },
                    ],
                },
            ],
        })
        assert len(world.records["sd-dcr.test"]) == 1
        assert world.records["sd-dcr.test"][0].collection == "com.example.test"

    def test_seed_from_dict_function_returns_world(self, pds_session):
        world = seed_from_dict(pds_session, {
            "accounts": [{"handle": "sd-dfn.test"}],
        })
        assert isinstance(world, World)


class TestSeedPlaceholders:
    """End-to-end tests for Seed.did() and Seed.ref() placeholder resolution."""

    def test_did_placeholder_resolves_in_record(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-did-a.test")
            .account("sd-did-b.test")
                .record("com.example.test", {
                    "$type": "com.example.test",
                    "performedBy": Seed.did("sd-did-a.test"),
                })
            .apply()
        )
        ref = world.records["sd-did-b.test"][0]
        rec = world.accounts["sd-did-b.test"].get_record(
            "com.example.test", ref.rkey,
        )
        assert rec["performedBy"] == world.accounts["sd-did-a.test"].did

    def test_ref_placeholder_resolves_in_record(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-ref-a.test")
                .record("com.example.data", {
                    "$type": "com.example.data",
                    "value": 42,
                })
            .account("sd-ref-b.test")
                .record("com.example.ref", {
                    "$type": "com.example.ref",
                    "target": Seed.ref("sd-ref-a.test", 0),
                })
            .apply()
        )
        bob_ref = world.records["sd-ref-b.test"][0]
        rec = world.accounts["sd-ref-b.test"].get_record(
            "com.example.ref", bob_ref.rkey,
        )
        alice_ref = world.records["sd-ref-a.test"][0]
        assert rec["target"]["uri"] == alice_ref.uri
        assert rec["target"]["cid"] == alice_ref.cid

    def test_nested_placeholders_resolve(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-nest-a.test")
                .record("com.example.data", {
                    "$type": "com.example.data",
                    "value": 1,
                })
            .account("sd-nest-b.test")
                .record("com.example.nested", {
                    "$type": "com.example.nested",
                    "outer": {
                        "actor": Seed.did("sd-nest-a.test"),
                        "refs": [Seed.ref("sd-nest-a.test", 0)],
                    },
                })
            .apply()
        )
        bob_ref = world.records["sd-nest-b.test"][0]
        rec = world.accounts["sd-nest-b.test"].get_record(
            "com.example.nested", bob_ref.rkey,
        )
        assert rec["outer"]["actor"] == world.accounts["sd-nest-a.test"].did
        assert rec["outer"]["refs"][0]["uri"] == world.records["sd-nest-a.test"][0].uri

    def test_ref_forward_reference_raises(self, pds_session):
        builder = (
            Seed(pds_session)
            .account("sd-fwd.test")
                .record("com.example.ref", {
                    "$type": "com.example.ref",
                    "target": Seed.ref("sd-fwd.test", 0),
                })
                .record("com.example.data", {
                    "$type": "com.example.data",
                    "value": 1,
                })
        )
        with pytest.raises(IndexError, match="record index 0"):
            builder.apply()


class TestSeedAccountRevisiting:
    """End-to-end tests for account revisiting (context switching)."""

    def test_interleaved_posts_across_accounts(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-intl-a.test")
                .post("alice first")
            .account("sd-intl-b.test")
                .post("bob first")
            .account("sd-intl-a.test")
                .post("alice second")
            .apply()
        )
        assert len(world.accounts) == 2
        assert len(world.records["sd-intl-a.test"]) == 2
        assert len(world.records["sd-intl-b.test"]) == 1

    def test_revisit_does_not_create_duplicate_account(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-revis.test")
                .post("first")
            .account("sd-revis-b.test")
            .account("sd-revis.test")
                .post("second")
            .apply()
        )
        assert len(world.accounts) == 2
        alice = world.accounts["sd-revis.test"]
        assert alice.did.startswith("did:plc:")
        records = alice.list_records("app.bsky.feed.post")
        assert len(records) == 2


class TestSeedReadmeExample:
    """Validate the exact usage pattern from the README."""

    def test_readme_seed_example(self, pds_session):
        world = (
            Seed(pds_session)
            .account("sd-rdme-a.test")
                .post("Hello from Alice")
                .post("Another post")
            .account("sd-rdme-b.test")
                .post("Bob's first post")
                .follow("sd-rdme-a.test")
                .like("sd-rdme-a.test", 0)
            .apply()
        )

        alice = world.accounts["sd-rdme-a.test"]
        bob = world.accounts["sd-rdme-b.test"]
        assert len(world.records["sd-rdme-a.test"]) == 2
        assert len(world.records["sd-rdme-b.test"]) == 1
        assert alice.did.startswith("did:plc:")
        assert bob.did.startswith("did:plc:")
