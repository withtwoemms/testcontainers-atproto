"""Integration tests: Seed builder and dict-based seeding end-to-end."""

import pytest

from testcontainers_atproto import PDSContainer, RecordRef
from testcontainers_atproto.seed import Seed, seed_from_dict
from testcontainers_atproto.world import World

pytestmark = pytest.mark.requires_docker


class TestSeedBuilderApply:
    """End-to-end seed-apply cycle with the fluent builder."""

    def test_single_account_no_records(self):
        with PDSContainer() as pds:
            world = Seed(pds).account("alice.test").apply()
            assert "alice.test" in world.accounts
            assert world.records["alice.test"] == []

    def test_single_account_with_posts(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .post("first")
                    .post("second")
                .apply()
            )
            assert len(world.records["alice.test"]) == 2
            assert all(isinstance(r, RecordRef) for r in world.records["alice.test"])

    def test_multi_account_record_counts(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .post("Hello from Alice")
                    .post("Another post")
                .account("bob.test")
                    .post("Bob's first post")
                .apply()
            )
            assert len(world.accounts) == 2
            assert len(world.records["alice.test"]) == 2
            assert len(world.records["bob.test"]) == 1

    def test_follow_creates_graph_record(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                .account("bob.test")
                    .follow("alice.test")
                .apply()
            )
            bob = world.accounts["bob.test"]
            alice = world.accounts["alice.test"]
            follows = bob.list_records("app.bsky.graph.follow")
            assert len(follows) == 1
            assert follows[0]["value"]["subject"] == alice.did

    def test_like_resolves_cross_account_ref(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .post("likeable post")
                .account("bob.test")
                    .like("alice.test", 0)
                .apply()
            )
            bob = world.accounts["bob.test"]
            likes = bob.list_records("app.bsky.feed.like")
            assert len(likes) == 1
            like_subject = likes[0]["value"]["subject"]
            assert like_subject["uri"] == world.records["alice.test"][0].uri

    def test_repost_resolves_cross_account_ref(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .post("repostable")
                .account("bob.test")
                    .repost("alice.test", 0)
                .apply()
            )
            bob = world.accounts["bob.test"]
            reposts = bob.list_records("app.bsky.feed.repost")
            assert len(reposts) == 1
            repost_subject = reposts[0]["value"]["subject"]
            assert repost_subject["uri"] == world.records["alice.test"][0].uri

    def test_custom_collection_record(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .record("com.example.test", {
                        "$type": "com.example.test",
                        "value": 42,
                    })
                .apply()
            )
            ref = world.records["alice.test"][0]
            assert ref.collection == "com.example.test"

    def test_record_with_explicit_rkey(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .record(
                        "com.example.test",
                        {"$type": "com.example.test", "value": 1},
                        rkey="mykey",
                    )
                .apply()
            )
            assert world.records["alice.test"][0].rkey == "mykey"

    def test_like_out_of_range_raises(self):
        with PDSContainer() as pds:
            builder = (
                Seed(pds)
                .account("alice.test")
                    .post("only post")
                .account("bob.test")
                    .like("alice.test", 99)
            )
            with pytest.raises(IndexError, match="record index 99"):
                builder.apply()

    def test_blob_upload(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .blob(b"test blob data", "application/octet-stream")
                .apply()
            )
            assert len(world.blobs["alice.test"]) == 1
            assert world.blobs["alice.test"][0]["$type"] == "blob"

    def test_world_is_instance(self):
        with PDSContainer() as pds:
            world = Seed(pds).account("alice.test").apply()
            assert isinstance(world, World)


class TestSeedDictApply:
    """End-to-end seed-apply cycle with the dict-based API."""

    def test_pds_seed_method(self):
        with PDSContainer() as pds:
            world = pds.seed({"accounts": [{"handle": "alice.test"}]})
            assert isinstance(world, World)
            assert "alice.test" in world.accounts

    def test_dict_with_posts_and_follows(self):
        with PDSContainer() as pds:
            world = seed_from_dict(pds, {
                "accounts": [
                    {
                        "handle": "alice.test",
                        "posts": ["Hello from Alice"],
                    },
                    {
                        "handle": "bob.test",
                        "posts": ["Hi from Bob"],
                        "follows": ["alice.test"],
                    },
                ],
            })
            assert len(world.records["alice.test"]) == 1
            assert len(world.records["bob.test"]) == 1
            bob = world.accounts["bob.test"]
            follows = bob.list_records("app.bsky.graph.follow")
            assert len(follows) == 1

    def test_dict_with_likes(self):
        with PDSContainer() as pds:
            world = seed_from_dict(pds, {
                "accounts": [
                    {
                        "handle": "alice.test",
                        "posts": ["Likeable post"],
                    },
                    {
                        "handle": "bob.test",
                        "likes": [{"handle": "alice.test", "index": 0}],
                    },
                ],
            })
            bob = world.accounts["bob.test"]
            likes = bob.list_records("app.bsky.feed.like")
            assert len(likes) == 1

    def test_dict_with_custom_records(self):
        with PDSContainer() as pds:
            world = seed_from_dict(pds, {
                "accounts": [
                    {
                        "handle": "alice.test",
                        "records": [
                            {
                                "collection": "com.example.test",
                                "record": {"$type": "com.example.test", "v": 1},
                            },
                        ],
                    },
                ],
            })
            assert len(world.records["alice.test"]) == 1
            assert world.records["alice.test"][0].collection == "com.example.test"

    def test_seed_from_dict_function_returns_world(self):
        with PDSContainer() as pds:
            world = seed_from_dict(pds, {
                "accounts": [{"handle": "alice.test"}],
            })
            assert isinstance(world, World)


class TestSeedReadmeExample:
    """Validate the exact usage pattern from the README."""

    def test_readme_seed_example(self):
        with PDSContainer() as pds:
            world = (
                Seed(pds)
                .account("alice.test")
                    .post("Hello from Alice")
                    .post("Another post")
                .account("bob.test")
                    .post("Bob's first post")
                    .follow("alice.test")
                    .like("alice.test", 0)
                .apply()
            )

            alice = world.accounts["alice.test"]
            bob = world.accounts["bob.test"]
            assert len(world.records["alice.test"]) == 2
            assert len(world.records["bob.test"]) == 1
            assert alice.did.startswith("did:plc:")
            assert bob.did.startswith("did:plc:")
