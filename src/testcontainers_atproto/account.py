# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Account: an authenticated ATP account on a PDS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from testcontainers_atproto.ref import RecordRef

if TYPE_CHECKING:
    from testcontainers_atproto.container import PDSContainer


class Account:
    """An authenticated ATP account on a PDS."""

    def __init__(
        self,
        pds: "PDSContainer",
        did: str,
        handle: str,
        access_jwt: str,
        refresh_jwt: str,
    ) -> None:
        self._pds = pds
        self._did = did
        self._handle = handle
        self._access_jwt = access_jwt
        self._refresh_jwt = refresh_jwt

    # --- Properties ---

    @property
    def did(self) -> str:
        """The account's DID (``did:plc:...``)."""
        return self._did

    @property
    def handle(self) -> str:
        """The account's handle."""
        return self._handle

    @property
    def access_jwt(self) -> str:
        """The account's access JWT."""
        return self._access_jwt

    @property
    def refresh_jwt(self) -> str:
        """The account's refresh JWT."""
        return self._refresh_jwt

    # --- Record Operations ---

    def create_record(
        self,
        collection: str,
        record: dict,
        rkey: Optional[str] = None,
        validate: bool = False,
    ) -> RecordRef:
        """Create a record in this account's repo."""
        raise NotImplementedError

    def get_record(self, collection: str, rkey: str) -> dict:
        """Fetch a record's value from this account's repo."""
        raise NotImplementedError

    def list_records(self, collection: str, limit: int = 50) -> list[dict]:
        """List records in a collection in this account's repo."""
        raise NotImplementedError

    def delete_record(self, collection: str, rkey: str) -> None:
        """Delete a record from this account's repo."""
        raise NotImplementedError

    def put_record(
        self,
        collection: str,
        rkey: str,
        record: dict,
    ) -> RecordRef:
        """Create or update a record (upsert)."""
        raise NotImplementedError

    def upload_blob(self, data: bytes, mime_type: str) -> dict:
        """Upload a blob and return the blob reference."""
        raise NotImplementedError

    # --- Convenience ---

    def strong_ref(self, collection: str, rkey: str) -> dict:
        """Get a strongRef dict for a record in this repo."""
        raise NotImplementedError

    def refresh_session(self) -> None:
        """Refresh the access token using the refresh token."""
        raise NotImplementedError
