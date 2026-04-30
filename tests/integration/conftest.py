"""Integration test configuration: shared container fixtures."""

import pytest

from testcontainers_atproto import PDSContainer


@pytest.fixture(scope="session")
def pds_session():
    """Shared PDS instance for the entire test session.

    All tests that use default PDSContainer config and unique handles
    share this single container.
    """
    with PDSContainer() as pds:
        yield pds


@pytest.fixture(scope="session")
def pds_email_session():
    """Shared PDS with email capture (Mailpit) for the session."""
    with PDSContainer(email_mode="capture") as pds:
        yield pds


@pytest.fixture(scope="session")
def pds_real_plc_session():
    """Shared PDS with Postgres-backed PLC directory for the session."""
    with PDSContainer(plc_mode="real") as pds:
        yield pds


@pytest.fixture(scope="module")
def pds_module(pds_session):
    """Module-scoped alias — delegates to the session-scoped container."""
    return pds_session
