"""Pytest fixtures for testcontainers-atproto.

Registered as a pytest plugin via the ``pytest11`` entry point. After
``pip install testcontainers-atproto`` users get the ``pds``, ``pds_module``,
and ``pds_pair`` fixtures automatically.
"""

from __future__ import annotations

import os
from typing import Iterator, Tuple

import pytest

from testcontainers_atproto.container import PDSContainer

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
    """Two ephemeral PDS instances for federation testing."""
    with PDSContainer(image=pds_image) as pds_a, PDSContainer(image=pds_image) as pds_b:
        yield pds_a, pds_b
