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
