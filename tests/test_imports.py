# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Sanity tests: package imports cleanly and RecordRef behaves."""

import pytest

from testcontainers_atproto import Account, PDSContainer, RecordRef


def test_top_level_exports_are_classes():
    assert isinstance(Account, type)
    assert isinstance(PDSContainer, type)
    assert isinstance(RecordRef, type)


def test_record_ref_parses_at_uri():
    ref = RecordRef(
        uri="at://did:plc:abc123/dev.calico.certificate/3k4f5xyz",
        cid="bafyreiabc",
    )
    assert ref.did == "did:plc:abc123"
    assert ref.collection == "dev.calico.certificate"
    assert ref.rkey == "3k4f5xyz"


def test_record_ref_as_strong_ref():
    ref = RecordRef(uri="at://did:plc:x/col.lection/r", cid="bafy")
    assert ref.as_strong_ref() == {"uri": "at://did:plc:x/col.lection/r", "cid": "bafy"}


def test_record_ref_rejects_bad_uri():
    with pytest.raises(ValueError):
        RecordRef(uri="https://example.com/not-at-uri", cid="bafy")
    with pytest.raises(ValueError):
        RecordRef(uri="at://did:plc:x/col.lection", cid="bafy")  # missing rkey


def test_fixtures_module_importable():
    # Registered via pytest11 entry point. Importable means pytest can load it.
    from testcontainers_atproto import fixtures

    assert hasattr(fixtures, "pds")
    assert hasattr(fixtures, "pds_pair")
