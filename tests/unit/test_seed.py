"""Unit tests: Seed builder state accumulation and validation."""

import pytest

from testcontainers_atproto.seed import Seed


class TestSeedAccountDeclaration:
    """Seed.account() manages account declarations."""

    def test_account_appends_to_decls(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        assert len(builder._account_decls) == 1
        assert builder._account_decls[0].handle == "alice.test"

    def test_account_sets_current_handle(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        assert builder._current_handle == "alice.test"

    def test_account_returns_self(self):
        builder = Seed(pds=None)
        result = builder.account("alice.test")
        assert result is builder

    def test_duplicate_handle_raises(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        with pytest.raises(ValueError, match="Duplicate account handle"):
            builder.account("alice.test")

    def test_multiple_accounts(self):
        builder = Seed(pds=None)
        builder.account("alice.test").account("bob.test")
        assert len(builder._account_decls) == 2
        assert builder._account_decls[0].handle == "alice.test"
        assert builder._account_decls[1].handle == "bob.test"

    def test_account_switches_context(self):
        builder = Seed(pds=None)
        builder.account("alice.test").account("bob.test")
        assert builder._current_handle == "bob.test"


class TestSeedPostDeclaration:
    """Seed.post() accumulates record declarations."""

    def test_post_appends_record_decl(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hello")
        assert len(builder._record_decls) == 1

    def test_post_collection_is_feed_post(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hello")
        assert builder._record_decls[0].collection == "app.bsky.feed.post"

    def test_post_record_has_text(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hello world")
        assert builder._record_decls[0].record["text"] == "hello world"

    def test_post_record_has_type(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hello")
        assert builder._record_decls[0].record["$type"] == "app.bsky.feed.post"

    def test_post_record_has_created_at(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hello")
        assert "createdAt" in builder._record_decls[0].record

    def test_post_without_account_raises(self):
        builder = Seed(pds=None)
        with pytest.raises(ValueError, match="No account context"):
            builder.post("hello")

    def test_post_returns_self(self):
        builder = Seed(pds=None)
        result = builder.account("alice.test").post("hello")
        assert result is builder

    def test_multiple_posts_preserve_order(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("first").post("second").post("third")
        texts = [d.record["text"] for d in builder._record_decls]
        assert texts == ["first", "second", "third"]

    def test_post_tracks_handle(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("a")
        builder.account("bob.test").post("b")
        assert builder._record_decls[0].handle == "alice.test"
        assert builder._record_decls[1].handle == "bob.test"


class TestSeedRecordDeclaration:
    """Seed.record() accumulates arbitrary record declarations."""

    def test_record_stores_collection(self):
        builder = Seed(pds=None)
        builder.account("alice.test").record("com.example.test", {"value": 42})
        assert builder._record_decls[0].collection == "com.example.test"

    def test_record_stores_record_dict(self):
        builder = Seed(pds=None)
        rec = {"$type": "com.example.test", "value": 42}
        builder.account("alice.test").record("com.example.test", rec)
        assert builder._record_decls[0].record == rec

    def test_record_with_rkey(self):
        builder = Seed(pds=None)
        builder.account("alice.test").record("com.example.test", {}, rkey="mykey")
        assert builder._record_decls[0].rkey == "mykey"

    def test_record_without_rkey(self):
        builder = Seed(pds=None)
        builder.account("alice.test").record("com.example.test", {})
        assert builder._record_decls[0].rkey is None

    def test_record_without_account_raises(self):
        builder = Seed(pds=None)
        with pytest.raises(ValueError, match="No account context"):
            builder.record("com.example.test", {})


class TestSeedFollowDeclaration:
    """Seed.follow() accumulates follow declarations."""

    def test_follow_stores_actor_and_target(self):
        builder = Seed(pds=None)
        builder.account("alice.test").account("bob.test").follow("alice.test")
        assert len(builder._follow_decls) == 1
        assert builder._follow_decls[0].actor_handle == "bob.test"
        assert builder._follow_decls[0].target_handle == "alice.test"

    def test_follow_undeclared_target_raises(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        with pytest.raises(ValueError, match="undeclared account"):
            builder.follow("unknown.test")

    def test_follow_returns_self(self):
        builder = Seed(pds=None)
        result = builder.account("alice.test").account("bob.test").follow("alice.test")
        assert result is builder


class TestSeedLikeDeclaration:
    """Seed.like() accumulates like declarations."""

    def test_like_stores_fields(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hi")
        builder.account("bob.test").like("alice.test", 0)
        assert len(builder._like_decls) == 1
        assert builder._like_decls[0].actor_handle == "bob.test"
        assert builder._like_decls[0].target_handle == "alice.test"
        assert builder._like_decls[0].target_record_index == 0

    def test_like_undeclared_target_raises(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        with pytest.raises(ValueError, match="undeclared account"):
            builder.like("unknown.test", 0)


class TestSeedRepostDeclaration:
    """Seed.repost() accumulates repost declarations."""

    def test_repost_stores_fields(self):
        builder = Seed(pds=None)
        builder.account("alice.test").post("hi")
        builder.account("bob.test").repost("alice.test", 0)
        assert len(builder._repost_decls) == 1
        assert builder._repost_decls[0].actor_handle == "bob.test"
        assert builder._repost_decls[0].target_handle == "alice.test"
        assert builder._repost_decls[0].target_record_index == 0

    def test_repost_undeclared_target_raises(self):
        builder = Seed(pds=None)
        builder.account("alice.test")
        with pytest.raises(ValueError, match="undeclared account"):
            builder.repost("unknown.test", 0)


class TestSeedBlobDeclaration:
    """Seed.blob() accumulates blob declarations."""

    def test_blob_stores_fields(self):
        builder = Seed(pds=None)
        builder.account("alice.test").blob(b"\x89PNG", "image/png")
        assert len(builder._blob_decls) == 1
        assert builder._blob_decls[0].handle == "alice.test"
        assert builder._blob_decls[0].data == b"\x89PNG"
        assert builder._blob_decls[0].mime_type == "image/png"

    def test_blob_default_mime_type(self):
        builder = Seed(pds=None)
        builder.account("alice.test").blob(b"data")
        assert builder._blob_decls[0].mime_type == "application/octet-stream"

    def test_blob_without_account_raises(self):
        builder = Seed(pds=None)
        with pytest.raises(ValueError, match="No account context"):
            builder.blob(b"data")


class TestSeedChaining:
    """Full builder chain produces expected internal state."""

    def test_full_chain(self):
        builder = (
            Seed(pds=None)
            .account("alice.test")
                .post("Hello from Alice")
                .post("Another post")
            .account("bob.test")
                .post("Bob's first post")
                .follow("alice.test")
                .like("alice.test", 0)
                .repost("alice.test", 1)
        )
        assert len(builder._account_decls) == 2
        assert len(builder._record_decls) == 3
        assert len(builder._follow_decls) == 1
        assert len(builder._like_decls) == 1
        assert len(builder._repost_decls) == 1
