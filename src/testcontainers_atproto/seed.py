"""Seed: declarative builder for PDS test state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from testcontainers_atproto.container import PDSContainer
    from testcontainers_atproto.world import World


# ---------------------------------------------------------------------------
# Internal operation dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _AccountDecl:
    handle: str


@dataclass
class _RecordDecl:
    handle: str
    collection: str
    record: dict
    rkey: Optional[str] = None


@dataclass
class _FollowDecl:
    actor_handle: str
    target_handle: str


@dataclass
class _LikeDecl:
    actor_handle: str
    target_handle: str
    target_record_index: int


@dataclass
class _RepostDecl:
    actor_handle: str
    target_handle: str
    target_record_index: int


@dataclass
class _BlobDecl:
    handle: str
    data: bytes
    mime_type: str


# ---------------------------------------------------------------------------
# Seed builder
# ---------------------------------------------------------------------------


class Seed:
    """Fluent builder for declarative PDS state.

    Usage::

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
    """

    def __init__(self, pds: PDSContainer) -> None:
        self._pds = pds
        self._current_handle: Optional[str] = None
        self._account_decls: list[_AccountDecl] = []
        self._record_decls: list[_RecordDecl] = []
        self._follow_decls: list[_FollowDecl] = []
        self._like_decls: list[_LikeDecl] = []
        self._repost_decls: list[_RepostDecl] = []
        self._blob_decls: list[_BlobDecl] = []
        self._seen_handles: set[str] = set()

    # --- Context ---

    def _require_account(self) -> str:
        """Return current handle or raise if no account context is set."""
        if self._current_handle is None:
            raise ValueError(
                "No account context. Call .account(handle) before "
                "adding records or interactions."
            )
        return self._current_handle

    # --- Declaration methods ---

    def account(self, handle: str) -> Seed:
        """Declare an account and switch builder context to it."""
        if handle in self._seen_handles:
            raise ValueError(f"Duplicate account handle: {handle!r}")
        self._seen_handles.add(handle)
        self._current_handle = handle
        self._account_decls.append(_AccountDecl(handle=handle))
        return self

    def post(self, text: str) -> Seed:
        """Add a post (``app.bsky.feed.post``) under the current account."""
        handle = self._require_account()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._record_decls.append(_RecordDecl(
            handle=handle,
            collection="app.bsky.feed.post",
            record={
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
            },
        ))
        return self

    def record(
        self,
        collection: str,
        record: dict,
        rkey: Optional[str] = None,
    ) -> Seed:
        """Add an arbitrary record under the current account."""
        handle = self._require_account()
        self._record_decls.append(_RecordDecl(
            handle=handle,
            collection=collection,
            record=record,
            rkey=rkey,
        ))
        return self

    def follow(self, target_handle: str) -> Seed:
        """Declare that the current account follows *target_handle*."""
        actor = self._require_account()
        if target_handle not in self._seen_handles:
            raise ValueError(
                f"Cannot follow undeclared account {target_handle!r}. "
                f"Declare it with .account({target_handle!r}) first."
            )
        self._follow_decls.append(_FollowDecl(
            actor_handle=actor,
            target_handle=target_handle,
        ))
        return self

    def like(self, target_handle: str, record_index: int) -> Seed:
        """Declare that the current account likes a record.

        Args:
            target_handle: Handle of the account whose record to like.
            record_index: Zero-based index into the target's declared records.
        """
        actor = self._require_account()
        if target_handle not in self._seen_handles:
            raise ValueError(
                f"Cannot like a record from undeclared account {target_handle!r}."
            )
        self._like_decls.append(_LikeDecl(
            actor_handle=actor,
            target_handle=target_handle,
            target_record_index=record_index,
        ))
        return self

    def repost(self, target_handle: str, record_index: int) -> Seed:
        """Declare that the current account reposts a record.

        Args:
            target_handle: Handle of the account whose record to repost.
            record_index: Zero-based index into the target's declared records.
        """
        actor = self._require_account()
        if target_handle not in self._seen_handles:
            raise ValueError(
                f"Cannot repost a record from undeclared account {target_handle!r}."
            )
        self._repost_decls.append(_RepostDecl(
            actor_handle=actor,
            target_handle=target_handle,
            target_record_index=record_index,
        ))
        return self

    def blob(self, data: bytes, mime_type: str = "application/octet-stream") -> Seed:
        """Upload a blob under the current account."""
        handle = self._require_account()
        self._blob_decls.append(_BlobDecl(
            handle=handle,
            data=data,
            mime_type=mime_type,
        ))
        return self

    # --- Execution ---

    def apply(self) -> World:
        """Materialize the declared state against the PDS.

        Execution order:

        1. Create all accounts
        2. Upload blobs, then create records (in declaration order)
        3. Create interactions (follows, likes, reposts)

        Returns:
            A :class:`~testcontainers_atproto.world.World` mapping handles
            to Account instances and ordered lists of RecordRefs.
        """
        from testcontainers_atproto.ref import RecordRef
        from testcontainers_atproto.world import World

        # Phase 1: accounts
        accounts = {}
        for decl in self._account_decls:
            accounts[decl.handle] = self._pds.create_account(decl.handle)

        # Phase 2a: blobs
        blobs: dict[str, list[dict]] = {h: [] for h in accounts}
        for decl in self._blob_decls:
            blob_ref = accounts[decl.handle].upload_blob(decl.data, decl.mime_type)
            blobs[decl.handle].append(blob_ref)

        # Phase 2b: records
        records: dict[str, list[RecordRef]] = {h: [] for h in accounts}
        for decl in self._record_decls:
            ref = accounts[decl.handle].create_record(
                decl.collection, decl.record, rkey=decl.rkey,
            )
            records[decl.handle].append(ref)

        # Phase 3: interactions
        self._apply_follows(accounts)
        self._apply_likes(accounts, records)
        self._apply_reposts(accounts, records)

        return World(accounts=accounts, records=records, blobs=blobs)

    def _apply_follows(self, accounts: dict) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for decl in self._follow_decls:
            actor = accounts[decl.actor_handle]
            target = accounts[decl.target_handle]
            actor.create_record("app.bsky.graph.follow", {
                "$type": "app.bsky.graph.follow",
                "subject": target.did,
                "createdAt": now,
            })

    def _apply_likes(self, accounts: dict, records: dict) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for decl in self._like_decls:
            actor = accounts[decl.actor_handle]
            target_records = records[decl.target_handle]
            if decl.target_record_index >= len(target_records):
                raise IndexError(
                    f"Like references record index {decl.target_record_index} "
                    f"for {decl.target_handle!r}, but only "
                    f"{len(target_records)} record(s) were declared."
                )
            target_ref = target_records[decl.target_record_index]
            actor.create_record("app.bsky.feed.like", {
                "$type": "app.bsky.feed.like",
                "subject": target_ref.as_strong_ref(),
                "createdAt": now,
            })

    def _apply_reposts(self, accounts: dict, records: dict) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for decl in self._repost_decls:
            actor = accounts[decl.actor_handle]
            target_records = records[decl.target_handle]
            if decl.target_record_index >= len(target_records):
                raise IndexError(
                    f"Repost references record index {decl.target_record_index} "
                    f"for {decl.target_handle!r}, but only "
                    f"{len(target_records)} record(s) were declared."
                )
            target_ref = target_records[decl.target_record_index]
            actor.create_record("app.bsky.feed.repost", {
                "$type": "app.bsky.feed.repost",
                "subject": target_ref.as_strong_ref(),
                "createdAt": now,
            })


# ---------------------------------------------------------------------------
# Dict-based API
# ---------------------------------------------------------------------------


def seed_from_dict(pds: PDSContainer, spec: dict) -> World:
    """Materialize PDS state from a plain dict specification.

    Dict shape::

        {
            "accounts": [
                {
                    "handle": "alice.test",
                    "posts": ["Hello"],
                    "records": [{"collection": "...", "record": {...}}],
                    "blobs": [{"data": b"...", "mime_type": "image/png"}],
                    "follows": ["bob.test"],
                    "likes": [{"handle": "alice.test", "index": 0}],
                    "reposts": [{"handle": "alice.test", "index": 0}],
                }
            ]
        }
    """
    builder = Seed(pds)
    for account_spec in spec.get("accounts", []):
        handle = account_spec["handle"]
        builder.account(handle)

        for text in account_spec.get("posts", []):
            builder.post(text)

        for rec_spec in account_spec.get("records", []):
            builder.record(
                rec_spec["collection"],
                rec_spec["record"],
                rkey=rec_spec.get("rkey"),
            )

        for blob_spec in account_spec.get("blobs", []):
            builder.blob(
                blob_spec["data"],
                blob_spec.get("mime_type", "application/octet-stream"),
            )

        for target in account_spec.get("follows", []):
            builder.follow(target)

        for like_spec in account_spec.get("likes", []):
            builder.like(like_spec["handle"], like_spec["index"])

        for repost_spec in account_spec.get("reposts", []):
            builder.repost(repost_spec["handle"], repost_spec["index"])

    return builder.apply()
