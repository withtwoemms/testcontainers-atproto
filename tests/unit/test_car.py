"""Unit tests: CAR v1 parser."""

import io

import cbor2
import pytest

from testcontainers_atproto.car import (
    CarBlock,
    CarFile,
    _HAS_CAR_DEPS,
    _read_varint,
    parse_car,
)


def _encode_varint(n: int) -> bytes:
    """Encode an unsigned LEB128 varint."""
    result = bytearray()
    while n > 0x7F:
        result.append((n & 0x7F) | 0x80)
        n >>= 7
    result.append(n & 0x7F)
    return bytes(result) if result else b"\x00"


def _build_car(roots=None, blocks=None) -> bytes:
    """Build a minimal CAR v1 byte string for testing."""
    if roots is None:
        roots = []
    if blocks is None:
        blocks = []

    header = cbor2.dumps({"version": 1, "roots": roots})

    buf = io.BytesIO()
    buf.write(_encode_varint(len(header)))
    buf.write(header)

    for cid_bytes, data in blocks:
        block_payload = cid_bytes + data
        buf.write(_encode_varint(len(block_payload)))
        buf.write(block_payload)

    return buf.getvalue()


class TestReadVarint:
    """_read_varint decodes unsigned LEB128 correctly."""

    def test_single_byte(self):
        assert _read_varint(io.BytesIO(b"\x05")) == 5

    def test_multi_byte(self):
        # 300 = 0b100101100 -> LEB128: 0xAC 0x02
        assert _read_varint(io.BytesIO(b"\xac\x02")) == 300

    def test_zero(self):
        assert _read_varint(io.BytesIO(b"\x00")) == 0

    def test_empty_stream_raises(self):
        with pytest.raises(ValueError, match="Unexpected end"):
            _read_varint(io.BytesIO(b""))


class TestParseCarHeader:
    """parse_car correctly decodes the CAR v1 header."""

    def test_empty_car(self):
        car_bytes = _build_car()
        result = parse_car(car_bytes)
        assert isinstance(result, CarFile)
        assert result.version == 1
        assert result.roots == []
        assert result.blocks == []

    def test_version_is_1(self):
        result = parse_car(_build_car())
        assert result.version == 1

    def test_unsupported_version_raises(self):
        header = cbor2.dumps({"version": 2, "roots": []})
        car_bytes = _encode_varint(len(header)) + header
        with pytest.raises(ValueError, match="Unsupported CAR version"):
            parse_car(car_bytes)


class TestParseCarBlocks:
    """parse_car correctly decodes blocks."""

    def test_single_block(self):
        # Fake CIDv0: 0x12 (sha2-256) + 0x20 (32 bytes) + 32 zero bytes
        fake_cid = b"\x12\x20" + b"\x00" * 32
        fake_data = b"hello block"
        car_bytes = _build_car(blocks=[(fake_cid, fake_data)])
        result = parse_car(car_bytes)
        assert len(result.blocks) == 1
        assert result.blocks[0].cid == fake_cid
        assert result.blocks[0].data == fake_data

    def test_multiple_blocks(self):
        fake_cid_1 = b"\x12\x20" + b"\x01" * 32
        fake_cid_2 = b"\x12\x20" + b"\x02" * 32
        car_bytes = _build_car(blocks=[
            (fake_cid_1, b"block one"),
            (fake_cid_2, b"block two"),
        ])
        result = parse_car(car_bytes)
        assert len(result.blocks) == 2
        assert result.blocks[0].data == b"block one"
        assert result.blocks[1].data == b"block two"


class TestCarFileDataclass:
    """CarFile and CarBlock are frozen dataclasses."""

    def test_car_file_is_frozen(self):
        cf = CarFile(version=1, roots=[], blocks=[])
        with pytest.raises(AttributeError):
            cf.version = 2  # type: ignore

    def test_car_block_is_frozen(self):
        cb = CarBlock(cid=b"\x00", data=b"\x01")
        with pytest.raises(AttributeError):
            cb.cid = b"\xff"  # type: ignore


class TestGuardedImport:
    """CAR module is importable and flag reflects installed deps."""

    def test_car_module_importable(self):
        assert isinstance(CarFile, type)
        assert isinstance(CarBlock, type)

    def test_has_car_deps_flag_is_true(self):
        # Test extras include [all] which pulls in cbor2.
        assert _HAS_CAR_DEPS is True
