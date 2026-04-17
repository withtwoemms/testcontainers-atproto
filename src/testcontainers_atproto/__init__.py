# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Testcontainers module for AT Protocol PDS integration testing."""

from importlib.metadata import version as _pkg_version

from testcontainers_atproto.account import Account
from testcontainers_atproto.container import PDSContainer
from testcontainers_atproto.ref import RecordRef

__all__ = [
    "Account",
    "PDSContainer",
    "RecordRef",
]

#: Derived by setuptools_scm from the latest git tag at build time.
__version__ = _pkg_version("testcontainers-atproto")

