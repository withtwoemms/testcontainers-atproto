# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""RecordRef: a typed reference to a record in an ATP repo."""

from __future__ import annotations

from dataclasses import dataclass

_AT_URI_PREFIX = "at://"


@dataclass(frozen=True)
class RecordRef:
    """Reference to a created/updated record.

    Attributes:
        uri: The AT URI of the record, e.g. ``at://did:plc:abc/col.lection/rkey``.
        cid: The content identifier (content hash) of the record.
    """

    uri: str
    cid: str

    def __post_init__(self) -> None:
        if not self.uri.startswith(_AT_URI_PREFIX):
            raise ValueError(
                f"uri must start with {_AT_URI_PREFIX!r}, got {self.uri!r}"
            )
        parts = self.uri[len(_AT_URI_PREFIX):].split("/")
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"uri must be of the form at://<did>/<collection>/<rkey>, got {self.uri!r}"
            )

    @property
    def did(self) -> str:
        """Extract the DID from the AT URI."""
        return self.uri[len(_AT_URI_PREFIX):].split("/", 1)[0]

    @property
    def collection(self) -> str:
        """Extract the collection NSID from the AT URI."""
        return self.uri[len(_AT_URI_PREFIX):].split("/")[1]

    @property
    def rkey(self) -> str:
        """Extract the rkey from the AT URI."""
        return self.uri[len(_AT_URI_PREFIX):].split("/")[2]

    def as_strong_ref(self) -> dict:
        """Return as a strongRef dict: ``{"uri": ..., "cid": ...}``."""
        return {"uri": self.uri, "cid": self.cid}
