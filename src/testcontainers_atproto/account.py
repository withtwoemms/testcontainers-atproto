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
        email: str = "",
    ) -> None:
        self._pds = pds
        self._did = did
        self._handle = handle
        self._access_jwt = access_jwt
        self._refresh_jwt = refresh_jwt
        self._email = email

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

    @property
    def email(self) -> str:
        """The account's email address."""
        return self._email

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

    # --- Email Verification ---

    def request_email_confirmation(self) -> None:
        """Request a confirmation email for this account.

        The PDS sends a verification email to the account's address.
        Retrieve it via ``pds.mailbox()`` or ``pds.await_email()``.

        Requires ``email_mode="capture"`` on the :class:`PDSContainer`.
        """
        self._pds.xrpc_post(
            "com.atproto.server.requestEmailConfirmation",
            auth=self._access_jwt,
        )

    def confirm_email(self, token: str) -> None:
        """Confirm email ownership using a token from the verification email.

        Args:
            token: The verification token extracted from the email.
        """
        self._pds.xrpc_post(
            "com.atproto.server.confirmEmail",
            data={"email": self._email, "token": token},
            auth=self._access_jwt,
        )

    def request_password_reset(self) -> None:
        """Request a password reset email for this account.

        The PDS sends a reset email to the account's address.
        Retrieve it via ``pds.mailbox()`` or ``pds.await_email()``.

        Requires ``email_mode="capture"`` on the :class:`PDSContainer`.
        """
        self._pds.xrpc_post(
            "com.atproto.server.requestPasswordReset",
            data={"email": self._email},
        )

    def reset_password(self, token: str, new_password: str) -> None:
        """Reset the account password using a token from the reset email.

        Args:
            token: The reset token extracted from the email.
            new_password: The new password to set.
        """
        self._pds.xrpc_post(
            "com.atproto.server.resetPassword",
            data={"token": token, "password": new_password},
        )

    # --- Account Lifecycle ---

    def deactivate(self, delete_after: Optional[str] = None) -> None:
        """Deactivate this account. Use activate() to re-enable."""
        data: dict = {}
        if delete_after is not None:
            data["deleteAfter"] = delete_after
        self._pds.xrpc_post(
            "com.atproto.server.deactivateAccount",
            data=data,
            auth=self._access_jwt,
        )

    def activate(self) -> None:
        """Re-activate a previously deactivated account."""
        self._pds.xrpc_post(
            "com.atproto.server.activateAccount",
            auth=self._access_jwt,
        )

    def check_account_status(self) -> dict:
        """Check this account's status (activated, validDid, repo stats)."""
        return self._pds.xrpc_get(
            "com.atproto.server.checkAccountStatus",
            auth=self._access_jwt,
        )

    def request_account_delete(self) -> None:
        """Request deletion token via email. Requires email_mode='capture'."""
        self._pds.xrpc_post(
            "com.atproto.server.requestAccountDelete",
            auth=self._access_jwt,
        )

    def delete_account(self, password: str, token: str) -> None:
        """Delete this account permanently."""
        self._pds.xrpc_post(
            "com.atproto.server.deleteAccount",
            data={
                "did": self._did,
                "password": password,
                "token": token,
            },
        )

    # --- Repo Sync ---

    def export_repo(self) -> bytes:
        """Export this account's repository as raw CAR bytes.

        Calls ``com.atproto.sync.getRepo`` and returns the binary
        CAR (Content Addressable aRchive) response.
        """
        return self._pds.sync_get(
            "com.atproto.sync.getRepo",
            params={"did": self._did},
        )

    def get_blob(self, cid: str) -> bytes:
        """Retrieve a blob by CID from this account's repository.

        Calls ``com.atproto.sync.getBlob`` and returns the raw blob bytes.

        Args:
            cid: The content identifier of the blob (the ``$link``
                value from the blob reference returned by
                :meth:`upload_blob`).
        """
        return self._pds.sync_get(
            "com.atproto.sync.getBlob",
            params={"did": self._did, "cid": cid},
        )
