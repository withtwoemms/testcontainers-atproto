# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""PDSContainer: an ephemeral AT Protocol PDS for testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from testcontainers_atproto.account import Account
    from testcontainers_atproto.firehose import FirehoseSubscription


class PDSContainer:
    """An ephemeral AT Protocol PDS for testing.

    Wraps ``ghcr.io/bluesky-social/pds`` with auto-generated configuration
    and a health check against ``GET /xrpc/_health``.
    """

    def __init__(
        self,
        image: str = "ghcr.io/bluesky-social/pds:0.4",
        hostname: str = "localhost",
        admin_password: Optional[str] = None,
    ) -> None:
        self._image = image
        self._hostname = hostname
        self._admin_password = admin_password
        raise NotImplementedError("PDSContainer.__init__ is not yet implemented")

    def __enter__(self) -> "PDSContainer":
        """Start the container, wait for health check."""
        raise NotImplementedError

    def __exit__(self, *args: object) -> None:
        """Stop and remove the container."""
        raise NotImplementedError

    # --- Properties ---

    @property
    def base_url(self) -> str:
        """XRPC base URL, e.g. ``http://localhost:53421``."""
        raise NotImplementedError

    @property
    def admin_password(self) -> str:
        """The admin password for this PDS instance."""
        raise NotImplementedError

    @property
    def host(self) -> str:
        """Container hostname as seen from the host machine."""
        raise NotImplementedError

    @property
    def port(self) -> int:
        """Mapped port for the PDS (3000 inside, dynamic outside)."""
        raise NotImplementedError

    # --- Account Management ---

    def create_account(
        self,
        handle: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> "Account":
        """Create an account on this PDS via the admin invite flow."""
        raise NotImplementedError

    # --- Raw XRPC ---

    def xrpc_get(
        self,
        method: str,
        params: Optional[dict] = None,
        auth: Optional[str] = None,
    ) -> dict:
        """Raw XRPC query (HTTP GET)."""
        raise NotImplementedError

    def xrpc_post(
        self,
        method: str,
        data: Optional[dict] = None,
        auth: Optional[str] = None,
    ) -> dict:
        """Raw XRPC procedure (HTTP POST)."""
        raise NotImplementedError

    # --- Health ---

    def health(self) -> dict:
        """Check PDS health. Returns ``{"version": "..."}``."""
        raise NotImplementedError

    # --- Firehose ---

    def subscribe(self, cursor: int = 0) -> "FirehoseSubscription":
        """Subscribe to ``com.atproto.sync.subscribeRepos``.

        Requires the ``firehose`` optional dependency group.
        """
        raise NotImplementedError
