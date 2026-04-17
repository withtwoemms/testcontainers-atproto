# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""PDSContainer: an ephemeral AT Protocol PDS for testing."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Optional

import httpx
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from testcontainers_atproto.account import Account

if TYPE_CHECKING:
    from testcontainers_atproto.firehose import FirehoseSubscription

_INTERNAL_PORT = 3000


class PDSContainer(DockerContainer):
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
        self._hostname = hostname
        self._admin_password = admin_password or secrets.token_hex(16)
        self._jwt_secret = secrets.token_hex(16)
        self._plc_rotation_key = secrets.token_hex(32)

        super().__init__(
            image,
            _wait_strategy=(
                HttpWaitStrategy(_INTERNAL_PORT, "/xrpc/_health")
                .for_response_predicate(lambda body: "version" in body)
                .with_startup_timeout(60)
                .with_poll_interval(0.5)
            ),
        )

        self.with_exposed_ports(_INTERNAL_PORT)
        self.with_kwargs(tmpfs={"/pds": ""})
        self.with_env("PDS_HOSTNAME", self._hostname)
        self.with_env("PDS_PORT", str(_INTERNAL_PORT))
        self.with_env("PDS_DEV_MODE", "true")
        self.with_env("PDS_ADMIN_PASSWORD", self._admin_password)
        self.with_env("PDS_JWT_SECRET", self._jwt_secret)
        self.with_env("PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX", self._plc_rotation_key)
        self.with_env("PDS_DATA_DIRECTORY", "/pds")
        self.with_env("PDS_BLOBSTORE_DISK_LOCATION", "/pds/blocks")
        self.with_env("PDS_DID_PLC_URL", "https://plc.directory")
        self.with_env("PDS_SERVICE_HANDLE_DOMAINS", ".test")
        self.with_env("LOG_ENABLED", "true")

    # --- Properties ---

    @property
    def base_url(self) -> str:
        """XRPC base URL, e.g. ``http://localhost:53421``."""
        return f"http://{self.host}:{self.port}"

    @property
    def admin_password(self) -> str:
        """The admin password for this PDS instance."""
        return self._admin_password

    @property
    def host(self) -> str:
        """Container hostname as seen from the host machine."""
        return self.get_container_host_ip()

    @property
    def port(self) -> int:
        """Mapped port for the PDS (3000 inside, dynamic outside)."""
        return int(self.get_exposed_port(_INTERNAL_PORT))

    # --- Account Management ---

    def create_account(
        self,
        handle: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Account:
        """Create an account on this PDS via the admin invite flow.

        Handles must end in ``.test`` (matching ``PDS_SERVICE_HANDLE_DOMAINS``).
        """
        email = email or f"{handle.replace('.', '-')}@test.invalid"
        password = password or secrets.token_hex(12)

        invite_resp = httpx.post(
            f"{self.base_url}/xrpc/com.atproto.server.createInviteCode",
            json={"useCount": 1},
            auth=("admin", self._admin_password),
            timeout=10.0,
        )
        invite_resp.raise_for_status()
        invite_code = invite_resp.json()["code"]

        account_resp = httpx.post(
            f"{self.base_url}/xrpc/com.atproto.server.createAccount",
            json={
                "handle": handle,
                "email": email,
                "password": password,
                "inviteCode": invite_code,
            },
            timeout=10.0,
        )
        account_resp.raise_for_status()
        data = account_resp.json()

        return Account(
            pds=self,
            did=data["did"],
            handle=data["handle"],
            access_jwt=data["accessJwt"],
            refresh_jwt=data["refreshJwt"],
        )

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
