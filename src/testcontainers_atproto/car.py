"""CAR v1 parser: decode Content Addressable aRchive bytes into blocks.

Requires ``cbor2`` (available via the ``sync`` or ``firehose`` extras).
Install with: ``pip install testcontainers-atproto[sync]``
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List

try:
    import cbor2

    _HAS_CAR_DEPS = True
except ImportError:
    _HAS_CAR_DEPS = False


@dataclass(frozen=True)
class CarBlock:
    """A single block in a CAR file.

    Attributes:
        cid: The raw CID bytes for this block.
        data: The block's data payload.
    """

    cid: bytes
    data: bytes


@dataclass(frozen=True)
class CarFile:
    """Parsed CAR v1 file.

    Attributes:
        version: CAR format version (always 1 for CAR v1).
        roots: List of root CID objects from the CAR header.
        blocks: Ordered list of blocks in the CAR file.
    """

    version: int
    roots: list
    blocks: List[CarBlock] = field(default_factory=list)


def _read_varint(stream: io.BytesIO) -> int:
    """Read an unsigned LEB128 varint from *stream*."""
    result = 0
    shift = 0
    while True:
        byte_data = stream.read(1)
        if not byte_data:
            raise ValueError("Unexpected end of stream reading varint")
        byte = byte_data[0]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result


def _read_cid(stream: io.BytesIO) -> bytes:
    """Read a CID from *stream* and return the raw bytes.

    Handles both CIDv0 (starts with 0x12 = sha2-256 multihash)
    and CIDv1 (starts with a CID version varint).
    """
    start = stream.tell()
    first_byte = stream.read(1)
    if not first_byte:
        raise ValueError("Unexpected end of stream reading CID")

    if first_byte[0] == 0x12:
        # CIDv0: raw sha2-256 multihash = 0x12 (code) + 0x20 (length=32) + 32 bytes
        rest = stream.read(1 + 32)  # digest length byte + digest
        return first_byte + rest
    else:
        # CIDv1: version varint + codec varint + multihash
        stream.seek(start)
        _read_varint(stream)  # version (1)
        _read_varint(stream)  # codec
        # multihash: hash function code varint + digest size varint + digest
        _read_varint(stream)  # hash function code
        digest_size = _read_varint(stream)  # digest size
        stream.read(digest_size)  # digest bytes
        end = stream.tell()
        stream.seek(start)
        cid_bytes = stream.read(end - start)
        return cid_bytes


def parse_car(data: bytes) -> CarFile:
    """Parse CAR v1 bytes into a :class:`CarFile`.

    Requires ``cbor2`` (install via the ``sync`` or ``firehose`` extra).

    Args:
        data: Raw CAR bytes (e.g. from :meth:`Account.export_repo`).

    Returns:
        Parsed :class:`CarFile` with header metadata and blocks.

    Raises:
        ImportError: If ``cbor2`` is not installed.
        ValueError: If the data is not valid CAR v1.
    """
    if not _HAS_CAR_DEPS:
        raise ImportError(
            "CAR parsing requires the 'sync' extra. "
            "Install it with: pip install testcontainers-atproto[sync]"
        )

    stream = io.BytesIO(data)

    # --- Header ---
    header_len = _read_varint(stream)
    header_bytes = stream.read(header_len)
    if len(header_bytes) != header_len:
        raise ValueError("Truncated CAR header")
    header = cbor2.loads(header_bytes)

    version = header.get("version", 1)
    if version != 1:
        raise ValueError(f"Unsupported CAR version: {version}")

    roots = header.get("roots", [])

    # --- Blocks ---
    blocks: list[CarBlock] = []
    while stream.tell() < len(data):
        block_len = _read_varint(stream)
        if block_len == 0:
            break
        block_start = stream.tell()
        cid = _read_cid(stream)
        cid_len = stream.tell() - block_start
        data_len = block_len - cid_len
        if data_len < 0:
            raise ValueError("Block length shorter than CID")
        block_data = stream.read(data_len)
        blocks.append(CarBlock(cid=cid, data=block_data))

    return CarFile(version=version, roots=roots, blocks=blocks)
