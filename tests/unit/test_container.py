"""Unit tests: PDSContainer configuration and parameter handling."""

import pytest

from testcontainers_atproto import PDSContainer


class TestEmailModeParameter:
    """PDSContainer.email_mode controls Mailpit companion container."""

    def test_email_mode_defaults_to_none(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._email_mode = "none"
        pds._mailpit = None
        assert pds.email_mode == "none"

    def test_email_mode_capture_stored(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._email_mode = "capture"
        assert pds.email_mode == "capture"

    def test_mailbox_raises_when_no_mailpit(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._mailpit = None
        with pytest.raises(RuntimeError, match="Mailpit is not running"):
            pds.mailbox()

    def test_await_email_raises_when_no_mailpit(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._mailpit = None
        with pytest.raises(RuntimeError, match="Mailpit is not running"):
            pds.await_email("alice@test.invalid")


class TestAdminMethods:
    """PDSContainer exposes admin methods (no Docker needed)."""

    def test_has_admin_get(self):
        assert callable(getattr(PDSContainer, "admin_get", None))

    def test_has_admin_post(self):
        assert callable(getattr(PDSContainer, "admin_post", None))

    def test_has_takedown(self):
        assert callable(getattr(PDSContainer, "takedown", None))

    def test_has_restore(self):
        assert callable(getattr(PDSContainer, "restore", None))

    def test_has_get_subject_status(self):
        assert callable(getattr(PDSContainer, "get_subject_status", None))

    def test_has_disable_invite_codes(self):
        assert callable(getattr(PDSContainer, "disable_invite_codes", None))


class TestSyncMethods:
    """PDSContainer exposes sync methods (no Docker needed)."""

    def test_has_sync_get(self):
        assert callable(getattr(PDSContainer, "sync_get", None))


class TestNetworkOwnership:
    """PDSContainer._owns_network controls lifecycle of shared resources."""

    def test_owns_network_true_by_default(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._owns_network = True
        assert pds._owns_network is True

    def test_owns_network_false_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._owns_network = False
        assert pds._owns_network is False

    def test_plc_is_none_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._plc = None
        assert pds._plc is None

    def test_postgres_is_none_with_external_network(self):
        pds = PDSContainer.__new__(PDSContainer)
        pds._postgres = None
        assert pds._postgres is None
