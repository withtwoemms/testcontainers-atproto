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
        body: dict = {
            "repo": self._did,
            "collection": collection,
            "record": record,
            "validate": validate,
        }
        if rkey is not None:
            body["rkey"] = rkey
        resp = self._pds.xrpc_post(
            "com.atproto.repo.createRecord",
            data=body,
            auth=self._access_jwt,
        )
        return RecordRef(uri=resp["uri"], cid=resp["cid"])

    def get_record(self, collection: str, rkey: str) -> dict:
        """Fetch a record's value from this account's repo."""
        resp = self._pds.xrpc_get(
            "com.atproto.repo.getRecord",
            params={"repo": self._did, "collection": collection, "rkey": rkey},
            auth=self._access_jwt,
        )
        return resp["value"]

    def list_records(self, collection: str, limit: int = 50) -> list[dict]:
        """List records in a collection in this account's repo."""
        resp = self._pds.xrpc_get(
            "com.atproto.repo.listRecords",
            params={"repo": self._did, "collection": collection, "limit": limit},
            auth=self._access_jwt,
        )
        return resp["records"]

    def delete_record(self, collection: str, rkey: str) -> None:
        """Delete a record from this account's repo."""
        self._pds.xrpc_post(
            "com.atproto.repo.deleteRecord",
            data={"repo": self._did, "collection": collection, "rkey": rkey},
            auth=self._access_jwt,
        )

    def put_record(
        self,
        collection: str,
        rkey: str,
        record: dict,
    ) -> RecordRef:
        """Create or update a record (upsert)."""
        resp = self._pds.xrpc_post(
            "com.atproto.repo.putRecord",
            data={
                "repo": self._did,
                "collection": collection,
                "rkey": rkey,
                "record": record,
            },
            auth=self._access_jwt,
        )
        return RecordRef(uri=resp["uri"], cid=resp["cid"])

    def upload_blob(self, data: bytes, mime_type: str) -> dict:
        """Upload a blob and return the blob reference."""
        resp = self._pds.xrpc_post(
            "com.atproto.repo.uploadBlob",
            auth=self._access_jwt,
            content=data,
            content_type=mime_type,
        )
        return resp["blob"]

    # --- Convenience ---

    def strong_ref(self, collection: str, rkey: str) -> dict:
        """Get a strongRef dict for a record in this repo."""
        resp = self._pds.xrpc_get(
            "com.atproto.repo.getRecord",
            params={"repo": self._did, "collection": collection, "rkey": rkey},
            auth=self._access_jwt,
        )
        return {"uri": resp["uri"], "cid": resp["cid"]}

    def refresh_session(self) -> None:
        """Refresh the access token using the refresh token."""
        resp = self._pds.xrpc_post(
            "com.atproto.server.refreshSession",
            auth=self._refresh_jwt,
        )
        self._access_jwt = resp["accessJwt"]
        self._refresh_jwt = resp["refreshJwt"]
