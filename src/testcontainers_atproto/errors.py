# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Typed XRPC error hierarchy."""

from __future__ import annotations

import httpx


class XrpcError(Exception):
    """XRPC call failure with structured error info.

    Attributes:
        method: The XRPC method NSID that failed.
        status_code: The HTTP status code from the response.
        error: The XRPC error name (e.g. ``"InvalidRequest"``).
        message: The XRPC error message from the response body.
    """

    def __init__(
        self,
        method: str,
        status_code: int,
        error: str = "",
        message: str = "",
    ) -> None:
        self.method = method
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(
            f"XRPC {method} failed ({status_code}): {error}: {message}"
        )


def _raise_for_xrpc_status(response: httpx.Response, method: str) -> None:
    """Raise :class:`XrpcError` if *response* is not 2xx.

    Parses the structured ``{"error": ..., "message": ...}`` body returned
    by the PDS.  The original :class:`httpx.HTTPStatusError` is chained as
    ``__cause__``.
    """
    if response.is_success:
        return

    error = ""
    message = ""
    try:
        body = response.json()
        error = body.get("error", "")
        message = body.get("message", "")
    except Exception:
        pass

    exc = XrpcError(
        method=method,
        status_code=response.status_code,
        error=error,
        message=message,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as http_err:
        raise exc from http_err
