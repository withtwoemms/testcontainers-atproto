"""RelayContainer: an ephemeral AT Protocol Relay for testing."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Optional

import httpx
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import HttpWaitStrategy

if TYPE_CHECKING:
    from testcontainers_atproto.container import PDSContainer
    from testcontainers_atproto.firehose import FirehoseSubscription

_RELAY_IMAGE = "withtwoemms/indigo:relay-8c6cc1a856bc01593a627800008ef5522a099f73"
_RELAY_PORT = 2470


class RelayContainer(DockerContainer):
    """An ephemeral AT Protocol Relay for testing.

    Wraps a patched ``indigo`` relay image that supports
    ``RELAY_SKIP_HOST_CHECK=true`` for Docker-internal networking.
    Health check against ``GET /xrpc/_health``.

    Args:
        image: Docker image tag for the relay.
        admin_password: Admin password. If ``None``, a random one is generated.
        _network: Shared Docker network (managed by caller).
        _plc_url: PLC directory URL reachable from the Docker network.
    """

    def __init__(
        self,
        image: str = _RELAY_IMAGE,
        admin_password: Optional[str] = None,
        *,
        _network: Optional[Network] = None,
        _plc_url: Optional[str] = None,
    ) -> None:
        self._admin_password = admin_password or secrets.token_hex(16)
        self._plc_url = _plc_url or "https://plc.directory"

        super().__init__(
            image,
            _wait_strategy=(
                HttpWaitStrategy(_RELAY_PORT, "/xrpc/_health")
                .for_response_predicate(lambda body: "version" in body)
                .with_startup_timeout(60)
                .with_poll_interval(0.5)
            ),
        )

        if _network is not None:
            self.with_network(_network)
        self.with_network_aliases("relay")
        self.with_exposed_ports(_RELAY_PORT)
        self.with_kwargs(tmpfs={"/data": ""})

        self.with_env("RELAY_ADMIN_PASSWORD", self._admin_password)
        self.with_env("RELAY_PLC_HOST", self._plc_url)
        self.with_env("RELAY_ALLOW_INSECURE_HOSTS", "true")
        self.with_env("RELAY_SKIP_HOST_CHECK", "true")
        self.with_env("LOG_LEVEL", "warn")

    # --- Properties ---

    @property
    def base_url(self) -> str:
        """HTTP base URL, e.g. ``http://localhost:54321``."""
        return f"http://{self.host}:{self.port}"

    @property
    def admin_password(self) -> str:
        """The admin password for this relay instance."""
        return self._admin_password

    @property
    def host(self) -> str:
        """Container hostname as seen from the host machine."""
        return self.get_container_host_ip()

    @property
    def port(self) -> int:
        """Mapped port for the relay (2470 inside, dynamic outside)."""
        return int(self.get_exposed_port(_RELAY_PORT))

    # --- Crawl Management ---

    def request_crawl(self, hostname: str) -> None:
        """Request the relay to crawl a host.

        Calls ``com.atproto.sync.requestCrawl`` with admin auth.

        Args:
            hostname: Bare hostname (no scheme, no port) of the PDS
                to crawl, e.g. ``"pds-a.test"``.
        """
        resp = httpx.post(
            f"{self.base_url}/xrpc/com.atproto.sync.requestCrawl",
            json={"hostname": hostname},
            auth=("admin", self._admin_password),
            timeout=10.0,
        )
        resp.raise_for_status()

    def crawl_pds(self, pds: "PDSContainer") -> None:
        """Convenience: request crawl using a PDS's Docker network hostname.

        Args:
            pds: A :class:`~testcontainers_atproto.container.PDSContainer`
                on the same Docker network.
        """
        self.request_crawl(pds._hostname)

    def list_hosts(self) -> list[dict]:
        """List hosts known to the relay.

        Calls ``com.atproto.sync.listHosts``.
        """
        resp = httpx.get(
            f"{self.base_url}/xrpc/com.atproto.sync.listHosts",
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("hosts", [])

    # --- Firehose ---

    def subscribe(self, cursor: int = 0) -> "FirehoseSubscription":
        """Subscribe to the relay's aggregated firehose.

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

    # --- Health ---

    def health(self) -> dict:
        """Check relay health. Returns ``{"version": "..."}``."""
        resp = httpx.get(f"{self.base_url}/xrpc/_health", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
