"""Pytest fixtures for testcontainers-atproto.

Registered as a pytest plugin via the ``pytest11`` entry point. After
``pip install testcontainers-atproto`` users get the ``pds``, ``pds_module``,
and ``pds_pair`` fixtures automatically.
"""

from __future__ import annotations

import os
from typing import Iterator, Tuple

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import HttpWaitStrategy

from testcontainers_atproto.container import (
    PDSContainer,
    _PLC_IMAGE,
    _PLC_PORT,
)

_DEFAULT_IMAGE = "ghcr.io/bluesky-social/pds:0.4"


@pytest.fixture(scope="session")
def pds_image() -> str:
    """PDS image tag. Override via ``ATP_PDS_IMAGE`` env var."""
    return os.environ.get("ATP_PDS_IMAGE", _DEFAULT_IMAGE)


@pytest.fixture
def pds(pds_image: str) -> Iterator[PDSContainer]:
    """An ephemeral PDS instance. Fresh per test."""
    with PDSContainer(image=pds_image) as container:
        yield container


@pytest.fixture(scope="module")
def pds_module(pds_image: str) -> Iterator[PDSContainer]:
    """An ephemeral PDS instance. Shared within a test module."""
    with PDSContainer(image=pds_image) as container:
        yield container


@pytest.fixture
def pds_pair(pds_image: str) -> Iterator[Tuple[PDSContainer, PDSContainer]]:
    """Two federated PDS instances sharing a single PLC directory.

    Both containers share one Docker network and one PLC directory,
    so DIDs registered on one PDS are resolvable by the other.
    """
    network = Network()
    network.create()

    plc = DockerContainer(
        _PLC_IMAGE,
        _wait_strategy=(
            HttpWaitStrategy(_PLC_PORT, "/_health")
            .for_response_predicate(lambda body: "version" in body)
            .with_startup_timeout(30)
            .with_poll_interval(0.5)
        ),
    )
    plc.with_network(network)
    plc.with_network_aliases("plc")
    plc.with_exposed_ports(_PLC_PORT)
    plc.with_env("PORT", str(_PLC_PORT))
    plc.with_env("DEBUG_MODE", "1")
    plc.with_env("LOG_ENABLED", "true")
    plc.with_command("yarn run start")
    plc.with_kwargs(working_dir="/app/packages/server")

    plc_url = f"http://plc:{_PLC_PORT}"

    try:
        plc.start()
        with (
            PDSContainer(
                image=pds_image,
                hostname="pds-a.test",
                _network=network,
                _plc_url=plc_url,
            ) as pds_a,
            PDSContainer(
                image=pds_image,
                hostname="pds-b.test",
                _network=network,
                _plc_url=plc_url,
            ) as pds_b,
        ):
            # Attach the shared PLC container so tests can query it
            pds_a._shared_plc = plc
            pds_b._shared_plc = plc
            yield pds_a, pds_b
    finally:
        plc.stop(force=True, delete_volume=True)
        network.remove()
