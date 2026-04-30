"""Integration test configuration: shared container fixtures."""

import pytest

from testcontainers_atproto import PDSContainer


@pytest.fixture(scope="module")
def pds_module():
    """Shared PDS instance for tests that use unique handles.

    Module-scoped: one container per test file, torn down after all
    tests in the module complete.
    """
    with PDSContainer() as pds:
        yield pds
