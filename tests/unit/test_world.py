"""Unit tests: World construction and access."""

import pytest

from testcontainers_atproto.world import World


class TestWorldConstruction:
    """World dataclass construction and defaults."""

    def test_empty_world_has_empty_accounts(self):
        world = World()
        assert world.accounts == {}

    def test_empty_world_has_empty_records(self):
        world = World()
        assert world.records == {}

    def test_empty_world_has_empty_blobs(self):
        world = World()
        assert world.blobs == {}

    def test_world_is_frozen(self):
        world = World()
        with pytest.raises(AttributeError):
            world.accounts = {"alice.test": "fake"}

    def test_accounts_accessible_by_handle(self):
        world = World(accounts={"alice.test": "fake-account"})
        assert world.accounts["alice.test"] == "fake-account"

    def test_records_accessible_by_handle(self):
        world = World(records={"alice.test": ["ref1", "ref2"]})
        assert world.records["alice.test"] == ["ref1", "ref2"]

    def test_blobs_accessible_by_handle(self):
        world = World(blobs={"alice.test": [{"$type": "blob"}]})
        assert world.blobs["alice.test"] == [{"$type": "blob"}]
