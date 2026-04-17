# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Integration tests: PDSContainer lifecycle and properties."""

import httpx
import pytest

from testcontainers_atproto import PDSContainer

pytestmark = pytest.mark.requires_docker


class TestPDSContainerLifecycle:
    """Container starts, responds to health checks, and stops cleanly."""

    def test_container_boots_and_is_healthy(self):
        with PDSContainer() as pds:
            resp = httpx.get(f"{pds.base_url}/xrpc/_health", timeout=5.0)
            assert resp.status_code == 200
            assert "version" in resp.json()

    def test_base_url_is_reachable(self):
        with PDSContainer() as pds:
            assert pds.base_url.startswith("http://")
            resp = httpx.get(f"{pds.base_url}/xrpc/_health", timeout=5.0)
            resp.raise_for_status()

    def test_port_is_dynamic_not_3000(self):
        with PDSContainer() as pds:
            assert isinstance(pds.port, int)
            assert pds.port != 3000

    def test_admin_password_auto_generated(self):
        with PDSContainer() as pds:
            assert len(pds.admin_password) == 32  # token_hex(16) = 32 hex chars

    def test_custom_admin_password(self):
        with PDSContainer(admin_password="my-secret") as pds:
            assert pds.admin_password == "my-secret"

    def test_two_containers_get_different_ports(self):
        with PDSContainer() as pds1, PDSContainer() as pds2:
            assert pds1.port != pds2.port

    def test_container_stops_cleanly(self):
        """Port is unreachable after context manager exits."""
        with PDSContainer() as pds:
            url = f"{pds.base_url}/xrpc/_health"
            httpx.get(url, timeout=5.0).raise_for_status()
        with pytest.raises(httpx.ConnectError):
            httpx.get(url, timeout=2.0)

    def test_unknown_xrpc_method_returns_error(self):
        with PDSContainer() as pds:
            resp = httpx.get(
                f"{pds.base_url}/xrpc/com.atproto.nonexistent.method",
                timeout=5.0,
            )
            assert resp.status_code in (400, 404, 501)


class TestPDSContainerRealPLC:
    """Container boots with a Postgres-backed PLC directory."""

    def test_real_plc_mode_boots(self):
        with PDSContainer(plc_mode="real") as pds:
            resp = httpx.get(f"{pds.base_url}/xrpc/_health", timeout=5.0)
            assert resp.status_code == 200
            assert "version" in resp.json()


class TestPDSContainerStubs:
    """Unimplemented methods raise NotImplementedError."""

    def test_xrpc_get_not_implemented(self):
        with PDSContainer() as pds:
            with pytest.raises(NotImplementedError):
                pds.xrpc_get("com.atproto.server.describeServer")

    def test_xrpc_post_not_implemented(self):
        with PDSContainer() as pds:
            with pytest.raises(NotImplementedError):
                pds.xrpc_post("com.atproto.server.createSession")

    def test_health_not_implemented(self):
        with PDSContainer() as pds:
            with pytest.raises(NotImplementedError):
                pds.health()

    def test_subscribe_not_implemented(self):
        with PDSContainer() as pds:
            with pytest.raises(NotImplementedError):
                pds.subscribe()
