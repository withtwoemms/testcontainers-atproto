"""World: the materialized result of a Seed.apply() call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testcontainers_atproto.account import Account
    from testcontainers_atproto.ref import RecordRef


@dataclass(frozen=True)
class World:
    """Materialized PDS state from a declarative seed.

    Attributes:
        accounts: Handle → Account mapping.
        records: Handle → ordered list of RecordRefs (declaration order).
        blobs: Handle → ordered list of blob reference dicts.
    """

    accounts: dict[str, Account] = field(default_factory=dict)
    records: dict[str, list[RecordRef]] = field(default_factory=dict)
    blobs: dict[str, list[dict]] = field(default_factory=dict)
