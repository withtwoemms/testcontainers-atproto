"""Test configuration: Docker availability gating."""

import pytest


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        import docker

        client = docker.from_env(version="auto")
        client.ping()
        client.close()
        return True
    except Exception:
        return False


_HAS_DOCKER = _docker_available()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_docker: mark test as requiring a running Docker daemon",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if _HAS_DOCKER:
        return
    skip_docker = pytest.mark.skip(reason="Docker daemon not available")
    for item in items:
        if "requires_docker" in item.keywords:
            item.add_marker(skip_docker)
