"""Unit tests: XrpcError hierarchy and _raise_for_xrpc_status helper."""

import httpx
import pytest

from testcontainers_atproto.errors import XrpcError, _raise_for_xrpc_status


def _mock_response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    """Build an httpx.Response without making a real request."""
    request = httpx.Request("POST", "http://localhost/xrpc/test.method")
    if json_body is not None:
        return httpx.Response(status_code, json=json_body, request=request)
    return httpx.Response(status_code, text="Internal Server Error", request=request)


class TestXrpcError:
    """XrpcError stores structured XRPC failure info."""

    def test_attributes_are_stored(self):
        exc = XrpcError("com.atproto.repo.createRecord", 400, "InvalidRequest", "bad input")
        assert exc.method == "com.atproto.repo.createRecord"
        assert exc.status_code == 400
        assert exc.error == "InvalidRequest"
        assert exc.message == "bad input"

    def test_str_contains_method_and_status(self):
        exc = XrpcError("com.atproto.repo.getRecord", 404, "RecordNotFound", "gone")
        text = str(exc)
        assert "com.atproto.repo.getRecord" in text
        assert "404" in text

    def test_str_contains_error_and_message(self):
        exc = XrpcError("m", 400, "InvalidRequest", "bad")
        text = str(exc)
        assert "InvalidRequest" in text
        assert "bad" in text

    def test_empty_error_and_message_defaults(self):
        exc = XrpcError("m", 500)
        assert exc.error == ""
        assert exc.message == ""

    def test_is_exception(self):
        assert isinstance(XrpcError("m", 500), Exception)


class TestRaiseForXrpcStatus:
    """_raise_for_xrpc_status converts HTTP responses to XrpcError."""

    def test_success_does_not_raise(self):
        resp = _mock_response(200, {"version": "0.4.0"})
        _raise_for_xrpc_status(resp, "test.method")

    def test_400_raises_with_body_parsed(self):
        resp = _mock_response(400, {"error": "InvalidRequest", "message": "bad input"})
        with pytest.raises(XrpcError) as exc_info:
            _raise_for_xrpc_status(resp, "com.atproto.repo.createRecord")
        exc = exc_info.value
        assert exc.status_code == 400
        assert exc.error == "InvalidRequest"
        assert exc.message == "bad input"
        assert exc.method == "com.atproto.repo.createRecord"

    def test_500_raises_with_empty_body(self):
        resp = _mock_response(500)
        with pytest.raises(XrpcError) as exc_info:
            _raise_for_xrpc_status(resp, "test.method")
        assert exc_info.value.status_code == 500
        assert exc_info.value.error == ""
        assert exc_info.value.message == ""

    def test_chains_httpx_error_as_cause(self):
        resp = _mock_response(401, {"error": "AuthRequired", "message": "no token"})
        with pytest.raises(XrpcError) as exc_info:
            _raise_for_xrpc_status(resp, "test.method")
        assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)

    def test_unparseable_json_still_raises(self):
        request = httpx.Request("GET", "http://localhost/xrpc/test")
        resp = httpx.Response(502, text="<html>bad gateway</html>", request=request)
        with pytest.raises(XrpcError) as exc_info:
            _raise_for_xrpc_status(resp, "test.method")
        assert exc_info.value.status_code == 502
        assert exc_info.value.error == ""
