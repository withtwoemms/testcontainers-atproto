"""Testcontainers module for AT Protocol PDS integration testing."""

from importlib.metadata import version as _pkg_version

from testcontainers_atproto.account import Account
from testcontainers_atproto.car import CarBlock, CarFile, parse_car
from testcontainers_atproto.container import PDSContainer
from testcontainers_atproto.errors import XrpcError
from testcontainers_atproto.firehose import FirehoseSubscription
from testcontainers_atproto.rate_limit import CreateSession, RateLimitTarget
from testcontainers_atproto.ref import RecordRef
from testcontainers_atproto.seed import Seed, seed_from_dict
from testcontainers_atproto.world import World

__all__ = [
    "Account",
    "CarBlock",
    "CarFile",
    "CreateSession",
    "FirehoseSubscription",
    "PDSContainer",
    "RateLimitTarget",
    "RecordRef",
    "Seed",
    "World",
    "seed_from_dict",
    "XrpcError",
    "parse_car",
]

#: Derived by setuptools_scm from the latest git tag at build time.
__version__ = _pkg_version("testcontainers-atproto")

