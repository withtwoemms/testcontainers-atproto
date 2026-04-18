"""PDSContainer: an ephemeral AT Protocol PDS for testing."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Optional

import httpx
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import ExecWaitStrategy, HttpWaitStrategy

from testcontainers_atproto.account import Account
from testcontainers_atproto.errors import _raise_for_xrpc_status

if TYPE_CHECKING:
    from testcontainers_atproto.firehose import FirehoseSubscription

_INTERNAL_PORT = 3000
_PLC_IMAGE = (
    "ghcr.io/bluesky-social/did-method-plc"
    ":plc-c54aea0373e65df0b87f5bc81710007092f539b1"
)
_PLC_PORT = 2582
_POSTGRES_IMAGE = "postgres:14-alpine"
_POSTGRES_PORT = 5432
_MAILPIT_IMAGE = "axllent/mailpit:v1.21"
_MAILPIT_SMTP_PORT = 1025
_MAILPIT_API_PORT = 8025


class PDSContainer(DockerContainer):
    """An ephemeral AT Protocol PDS for testing.

    Wraps ``ghcr.io/bluesky-social/pds`` with auto-generated configuration
    and a health check against ``GET /xrpc/_health``.

    A local PLC directory runs alongside the PDS on a shared Docker network
    so that DID registration never touches the public internet.

    Args:
        plc_mode: ``"mock"`` (default) uses an in-memory PLC — fast, no
            Postgres. ``"real"`` adds a Postgres-backed PLC for production
            parity.
        email_mode: ``"none"`` (default) bypasses email verification.
            ``"capture"`` starts a Mailpit companion container and routes
            PDS emails through Mailpit for test retrieval via
            :meth:`mailbox` and :meth:`await_email`.
    """

    def __init__(
        self,
        image: str = "ghcr.io/bluesky-social/pds:0.4",
        hostname: str = "localhost",
        admin_password: Optional[str] = None,
        plc_mode: str = "mock",
        email_mode: str = "none",
    ) -> None:
        self._hostname = hostname
        self._admin_password = admin_password or secrets.token_hex(16)
        self._jwt_secret = secrets.token_hex(16)
        self._plc_rotation_key = secrets.token_hex(32)
        self._plc_mode = plc_mode

        # --- Docker network (shared by all companion containers) ---

        self._plc_network = Network()

        # --- PLC directory ---

        self._plc = DockerContainer(
            _PLC_IMAGE,
            _wait_strategy=(
                HttpWaitStrategy(_PLC_PORT, "/_health")
                .for_response_predicate(lambda body: "version" in body)
                .with_startup_timeout(30)
                .with_poll_interval(0.5)
            ),
        )
        self._plc.with_network(self._plc_network)
        self._plc.with_network_aliases("plc")
        self._plc.with_exposed_ports(_PLC_PORT)
        self._plc.with_env("PORT", str(_PLC_PORT))
        self._plc.with_env("DEBUG_MODE", "1")
        self._plc.with_env("LOG_ENABLED", "true")
        self._plc.with_command("yarn run start")
        self._plc.with_kwargs(working_dir="/app/packages/server")

        # --- Postgres (real mode only) ---

        if plc_mode == "real":
            self._postgres: Optional[DockerContainer] = DockerContainer(
                _POSTGRES_IMAGE,
                _wait_strategy=(
                    ExecWaitStrategy(["sh", "-c", "pg_isready -U plc"])
                    .with_startup_timeout(30)
                ),
            )
            self._postgres.with_network(self._plc_network)
            self._postgres.with_network_aliases("plcdb")
            self._postgres.with_exposed_ports(_POSTGRES_PORT)
            self._postgres.with_env("POSTGRES_USER", "plc")
            self._postgres.with_env("POSTGRES_PASSWORD", "plc")
            self._postgres.with_env("POSTGRES_DB", "plc")

            self._plc.with_env(
                "DATABASE_URL",
                f"postgres://plc:plc@plcdb:{_POSTGRES_PORT}/plc",
            )
        else:
            self._postgres = None

        # --- Mailpit (capture mode only) ---

        self._email_mode = email_mode

        if email_mode == "capture":
            self._mailpit: Optional[DockerContainer] = DockerContainer(
                _MAILPIT_IMAGE,
                _wait_strategy=(
                    HttpWaitStrategy(_MAILPIT_API_PORT, "/api/v1/messages")
                    .with_startup_timeout(30)
                    .with_poll_interval(0.5)
                ),
            )
            self._mailpit.with_network(self._plc_network)
            self._mailpit.with_network_aliases("mailpit")
            self._mailpit.with_exposed_ports(_MAILPIT_API_PORT)
        else:
            self._mailpit = None

        # --- PDS ---

        super().__init__(
            image,
            _wait_strategy=(
                HttpWaitStrategy(_INTERNAL_PORT, "/xrpc/_health")
                .for_response_predicate(lambda body: "version" in body)
                .with_startup_timeout(60)
                .with_poll_interval(0.5)
            ),
        )

        self.with_network(self._plc_network)
        self.with_exposed_ports(_INTERNAL_PORT)
        self.with_kwargs(tmpfs={"/pds": ""})
        self.with_env("PDS_HOSTNAME", self._hostname)
        self.with_env("PDS_PORT", str(_INTERNAL_PORT))
        self.with_env("PDS_DEV_MODE", "true")
        if email_mode == "capture":
            self.with_env(
                "PDS_EMAIL_SMTP_URL",
                f"smtp://mailpit:{_MAILPIT_SMTP_PORT}",
            )
            self.with_env("PDS_EMAIL_FROM_ADDRESS", "noreply@pds.test")
        self.with_env("PDS_ADMIN_PASSWORD", self._admin_password)
        self.with_env("PDS_JWT_SECRET", self._jwt_secret)
        self.with_env("PDS_PLC_ROTATION_KEY_K256_PRIVATE_KEY_HEX", self._plc_rotation_key)
        self.with_env("PDS_DATA_DIRECTORY", "/pds")
        self.with_env("PDS_BLOBSTORE_DISK_LOCATION", "/pds/blocks")
        self.with_env("PDS_DID_PLC_URL", f"http://plc:{_PLC_PORT}")
        self.with_env("PDS_SERVICE_HANDLE_DOMAINS", ".test")
        self.with_env("LOG_ENABLED", "true")

    # --- Lifecycle ---

    def start(self) -> "PDSContainer":
        """Start the network, companion containers, then the PDS."""
        self._plc_network.create()
        if self._postgres is not None:
            self._postgres.start()
        self._plc.start()
        if self._mailpit is not None:
            self._mailpit.start()
        return super().start()

    def stop(self, force=True, delete_volume=True) -> None:
        """Stop the PDS, companion containers, then remove the network."""
        super().stop(force, delete_volume)
        self._plc.stop(force, delete_volume)
        if self._postgres is not None:
            self._postgres.stop(force, delete_volume)
        if self._mailpit is not None:
            self._mailpit.stop(force, delete_volume)
        self._plc_network.remove()

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

    @property
    def email_mode(self) -> str:
        """The email mode: ``"none"`` or ``"capture"``."""
        return self._email_mode

    # --- Email (capture mode) ---

    def _mailpit_api_url(self) -> str:
        """Mailpit HTTP API base URL (host-side)."""
        if self._mailpit is None:
            raise RuntimeError(
                "Mailpit is not running. "
                "Use email_mode='capture' to enable email capture."
            )
        port = self._mailpit.get_exposed_port(_MAILPIT_API_PORT)
        host = self._mailpit.get_container_host_ip()
        return f"http://{host}:{port}"

    def mailbox(self, address: Optional[str] = None) -> list[dict]:
        """Retrieve captured emails from Mailpit.

        Requires ``email_mode="capture"``.

        Args:
            address: Optional recipient email address to filter by.

        Returns:
            List of message dicts from the Mailpit API.
        """
        url = self._mailpit_api_url()
        if address is not None:
            resp = httpx.get(
                f"{url}/api/v1/search",
                params={"query": f"to:{address}"},
                timeout=10.0,
            )
        else:
            resp = httpx.get(f"{url}/api/v1/messages", timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("messages", [])

    def await_email(
        self,
        address: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
    ) -> dict:
        """Poll Mailpit until an email for *address* arrives.

        Requires ``email_mode="capture"``.

        Args:
            address: Recipient email address to wait for.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls.

        Returns:
            The first matching message dict.

        Raises:
            TimeoutError: If no matching email arrives within *timeout*.
        """
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            messages = self.mailbox(address)
            if messages:
                return messages[0]
            time.sleep(poll_interval)
        raise TimeoutError(
            f"No email for {address!r} arrived within {timeout}s."
        )

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

        data = self.xrpc_post(
            "com.atproto.server.createAccount",
            data={
                "handle": handle,
                "email": email,
                "password": password,
                "inviteCode": invite_code,
            },
        )

        return Account(
            pds=self,
            did=data["did"],
            handle=data["handle"],
            access_jwt=data["accessJwt"],
            refresh_jwt=data["refreshJwt"],
            email=email,
        )

    # --- Raw XRPC ---

    def xrpc_get(
        self,
        method: str,
        params: Optional[dict] = None,
        auth: Optional[str] = None,
    ) -> dict:
        """Raw XRPC query (HTTP GET)."""
        headers: dict[str, str] = {}
        if auth is not None:
            headers["Authorization"] = f"Bearer {auth}"
        resp = httpx.get(
            f"{self.base_url}/xrpc/{method}",
            params=params,
            headers=headers,
            timeout=10.0,
        )
        _raise_for_xrpc_status(resp, method)
        if not resp.content:
            return {}
        return resp.json()

    def xrpc_post(
        self,
        method: str,
        data: Optional[dict] = None,
        auth: Optional[str] = None,
        *,
        content: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> dict:
        """Raw XRPC procedure (HTTP POST).

        For JSON payloads, pass *data*. For raw byte payloads (e.g. blob
        upload), pass *content* and *content_type* instead.
        """
        headers: dict[str, str] = {}
        if auth is not None:
            headers["Authorization"] = f"Bearer {auth}"

        if content is not None:
            headers["Content-Type"] = content_type or "application/octet-stream"
            resp = httpx.post(
                f"{self.base_url}/xrpc/{method}",
                content=content,
                headers=headers,
                timeout=10.0,
            )
        else:
            resp = httpx.post(
                f"{self.base_url}/xrpc/{method}",
                json=data,
                headers=headers,
                timeout=10.0,
            )
        _raise_for_xrpc_status(resp, method)
        if not resp.content:
            return {}
        return resp.json()

    # --- Health ---

    def health(self) -> dict:
        """Check PDS health. Returns ``{"version": "..."}``."""
        resp = httpx.get(f"{self.base_url}/xrpc/_health", timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    # --- Firehose ---

    def subscribe(self, cursor: int = 0) -> "FirehoseSubscription":
        """Subscribe to ``com.atproto.sync.subscribeRepos``.

        Requires the ``firehose`` optional dependency group.
        Install with: ``pip install testcontainers-atproto[firehose]``
        """
        from testcontainers_atproto.firehose import (
            FirehoseSubscription,
            _HAS_FIREHOSE_DEPS,
        )

        if not _HAS_FIREHOSE_DEPS:
            raise ImportError(
                "Firehose support requires the 'firehose' extra. "
                "Install it with: pip install testcontainers-atproto[firehose]"
            )

        ws_url = (
            f"ws://{self.host}:{self.port}"
            f"/xrpc/com.atproto.sync.subscribeRepos?cursor={cursor}"
        )
        return FirehoseSubscription(ws_url)

    def seed(self, spec: dict) -> "World":
        """Materialize PDS state from a dict specification.

        Convenience wrapper around
        :func:`~testcontainers_atproto.seed.seed_from_dict`.
        """
        from testcontainers_atproto.seed import seed_from_dict

        return seed_from_dict(self, spec)
