"""OAuth DPoP flow support for AT Protocol PDS testing.

Requires the ``oauth`` optional dependency group (``cryptography``, ``PyJWT``).
Install with: ``pip install testcontainers-atproto[oauth]``
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    import jwt as pyjwt

    _HAS_OAUTH_DEPS = True
except ImportError:
    _HAS_OAUTH_DEPS = False


def _check_deps() -> None:
    """Raise :class:`ImportError` if oauth deps are missing."""
    if not _HAS_OAUTH_DEPS:
        raise ImportError(
            "OAuth support requires the 'oauth' extra. "
            "Install it with: pip install testcontainers-atproto[oauth]"
        )


def _base64url(data: bytes) -> str:
    """Base64url-encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _int_to_base64url(n: int, length: int) -> str:
    """Encode a big integer as base64url."""
    return _base64url(n.to_bytes(length, "big"))


# ---------------------------------------------------------------------------
# PKCEChallenge
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PKCEChallenge:
    """A PKCE (S256) verifier/challenge pair.

    Uses only stdlib — no optional deps required.
    """

    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> PKCEChallenge:
        """Generate a random PKCE challenge pair."""
        verifier = _base64url(os.urandom(32))
        challenge = _base64url(hashlib.sha256(verifier.encode()).digest())
        return cls(verifier=verifier, challenge=challenge)


# ---------------------------------------------------------------------------
# DPoPKey
# ---------------------------------------------------------------------------


class DPoPKey:
    """An ES256 key pair for DPoP proof generation.

    Requires the ``oauth`` extra (``cryptography``, ``PyJWT``).
    """

    def __init__(self, private_key: object) -> None:
        _check_deps()
        self._private_key = private_key
        pub_nums = private_key.public_key().public_numbers()  # type: ignore[union-attr]
        self._public_jwk: dict = {
            "kty": "EC",
            "crv": "P-256",
            "x": _int_to_base64url(pub_nums.x, 32),
            "y": _int_to_base64url(pub_nums.y, 32),
        }

    @classmethod
    def generate(cls) -> DPoPKey:
        """Generate a new ES256 (P-256) key pair."""
        _check_deps()
        private_key = ec.generate_private_key(ec.SECP256R1())  # type: ignore[attr-defined]
        return cls(private_key)

    @property
    def public_jwk(self) -> dict:
        """The public JWK (for embedding in DPoP proof headers)."""
        return dict(self._public_jwk)

    def proof(
        self,
        htm: str,
        htu: str,
        nonce: Optional[str] = None,
        ath: Optional[str] = None,
    ) -> str:
        """Create a DPoP proof JWT.

        Args:
            htm: HTTP method (e.g. ``"POST"``).
            htu: HTTP target URI (must use the PDS issuer URL).
            nonce: Server-provided DPoP nonce.
            ath: Access token hash (base64url of SHA-256).
        """
        now = int(time.time())
        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": self._public_jwk}
        payload: dict = {
            "jti": str(uuid.uuid4()),
            "htm": htm,
            "htu": htu,
            "iat": now,
            "exp": now + 120,
        }
        if nonce:
            payload["nonce"] = nonce
        if ath:
            payload["ath"] = ath
        return pyjwt.encode(  # type: ignore[attr-defined]
            payload, self._private_key, algorithm="ES256", headers=header
        )

    @staticmethod
    def access_token_hash(access_token: str) -> str:
        """Compute the ``ath`` claim value for a DPoP proof."""
        return _base64url(hashlib.sha256(access_token.encode()).digest())


# ---------------------------------------------------------------------------
# OAuthTokens
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OAuthTokens:
    """Token response from the PDS OAuth token endpoint."""

    access_token: str
    token_type: str
    refresh_token: str
    scope: str
    expires_in: int
    sub: str

    @classmethod
    def from_response(cls, data: dict) -> OAuthTokens:
        """Parse a token endpoint JSON response."""
        return cls(
            access_token=data["access_token"],
            token_type=data["token_type"],
            refresh_token=data["refresh_token"],
            scope=data["scope"],
            expires_in=data["expires_in"],
            sub=data["sub"],
        )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _rewrite_url(internal_url: str, base_url: str) -> str:
    """Rewrite a PDS internal URL to the external mapped URL.

    The PDS reports its own internal URLs (e.g. ``http://localhost:3000/...``)
    in OAuth metadata.  We need to hit the Docker-mapped port instead.
    """
    parsed = urlparse(internal_url)
    base_parsed = urlparse(base_url)
    return internal_url.replace(
        f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
        f"{base_parsed.scheme}://{base_parsed.hostname}:{base_parsed.port}",
    )


def _dpop_aware_post(
    url: str,
    dpop_key: DPoPKey,
    htu: str,
    dpop_nonce: Optional[str],
    **kwargs: object,
) -> tuple[httpx.Response, str]:
    """POST with DPoP proof, retrying once on ``use_dpop_nonce``.

    Returns ``(response, current_dpop_nonce)``.
    """
    proof = dpop_key.proof("POST", htu, nonce=dpop_nonce)
    headers = dict(kwargs.pop("headers", {}) or {})  # type: ignore[arg-type]
    headers["DPoP"] = proof
    resp = httpx.post(url, headers=headers, **kwargs, timeout=10.0)  # type: ignore[arg-type]
    nonce = resp.headers.get("dpop-nonce", dpop_nonce or "")

    if resp.status_code == 400:
        body = resp.json()
        if body.get("error") == "use_dpop_nonce" and nonce:
            proof = dpop_key.proof("POST", htu, nonce=nonce)
            headers["DPoP"] = proof
            resp = httpx.post(url, headers=headers, **kwargs, timeout=10.0)  # type: ignore[arg-type]
            nonce = resp.headers.get("dpop-nonce", nonce)

    return resp, nonce


# ---------------------------------------------------------------------------
# OAuthClient
# ---------------------------------------------------------------------------

_API_PREFIX = "/@atproto/oauth-provider/~api"


class OAuthClient:
    """Low-level OAuth DPoP flow client for a PDS.

    Provides step-by-step methods for each phase of the OAuth flow:
    PAR, sign-in, consent, token exchange, refresh, and revocation.

    Args:
        base_url: External PDS URL (e.g. ``http://localhost:53421``).
        dpop_key: A :class:`DPoPKey` for DPoP proof generation.
        client_id: OAuth client ID. Defaults to the localhost format.
        scope: OAuth scope. Defaults to ``"atproto transition:generic"``.
    """

    def __init__(
        self,
        base_url: str,
        dpop_key: DPoPKey,
        client_id: str = (
            "http://localhost"
            "?redirect_uri=http://127.0.0.1:0/oauth/callback"
            "&scope=atproto+transition:generic"
        ),
        scope: str = "atproto transition:generic",
    ) -> None:
        _check_deps()
        self._base_url = base_url
        self._dpop_key = dpop_key
        self._client_id = client_id
        self._scope = scope
        self._dpop_nonce: Optional[str] = None
        self._metadata: Optional[dict] = None
        self._redirect_uri = "http://127.0.0.1:0/oauth/callback"

    # --- Discovery ---

    def discover(self) -> dict:
        """Fetch OAuth authorization server metadata.

        Returns:
            The parsed JSON metadata dict.
        """
        resp = httpx.get(
            f"{self._base_url}/.well-known/oauth-authorization-server",
            timeout=10.0,
        )
        resp.raise_for_status()
        self._metadata = resp.json()
        return self._metadata

    @property
    def metadata(self) -> dict:
        """Cached metadata (calls :meth:`discover` if needed)."""
        if self._metadata is None:
            self.discover()
        return self._metadata  # type: ignore[return-value]

    @property
    def issuer(self) -> str:
        """The PDS issuer URL (internal)."""
        return self.metadata["issuer"]

    # --- PAR ---

    def pushed_authorization_request(
        self, pkce: PKCEChallenge, state: Optional[str] = None, login_hint: Optional[str] = None,
    ) -> str:
        """Submit a Pushed Authorization Request.

        Args:
            pkce: PKCE challenge pair.
            state: OAuth state parameter.
            login_hint: Handle to pre-fill on the login form.

        Returns:
            The ``request_uri`` for use in the authorization step.
        """
        par_internal = self.metadata["pushed_authorization_request_endpoint"]
        par_ext = _rewrite_url(par_internal, self._base_url)

        data = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": self._scope,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
        }
        if state:
            data["state"] = state
        if login_hint:
            data["login_hint"] = login_hint

        resp, self._dpop_nonce = _dpop_aware_post(
            par_ext, self._dpop_key, par_internal, self._dpop_nonce, data=data,
        )
        resp.raise_for_status()
        body = resp.json()
        return body["request_uri"]

    # --- Authorize (sign-in + consent) ---

    def authorize(
        self,
        request_uri: str,
        username: str,
        password: str,
    ) -> str:
        """Perform programmatic sign-in and consent.

        This replaces what a browser would do: load the authorization page,
        sign in, and approve the consent screen.

        Args:
            request_uri: The ``request_uri`` from :meth:`pushed_authorization_request`.
            username: Account handle (e.g. ``"alice.test"``).
            password: Account password.

        Returns:
            The authorization code.
        """
        auth_ext = _rewrite_url(
            self.metadata["authorization_endpoint"], self._base_url
        )
        issuer = self.issuer

        with httpx.Client(follow_redirects=False, timeout=10.0) as client:
            # 1. GET the authorization page to obtain session cookies
            resp = client.get(
                auth_ext,
                params={
                    "client_id": self._client_id,
                    "request_uri": request_uri,
                },
                headers={
                    "Sec-Fetch-Site": "cross-site",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Dest": "document",
                },
            )
            resp.raise_for_status()

            # Extract cookies (including Secure ones that httpx won't resend over HTTP)
            cookies: dict[str, str] = {}
            for h_name, h_val in resp.headers.multi_items():
                if h_name.lower() == "set-cookie":
                    parts = h_val.split(";")[0].split("=", 1)
                    if len(parts) == 2:
                        cookies[parts[0].strip()] = parts[1].strip()

            csrf = cookies.get("csrf-token", "")
            origin = issuer
            referer = (
                f"{issuer}/oauth/authorize?"
                + urlencode({"client_id": self._client_id, "request_uri": request_uri})
            )
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

            api_headers = {
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": referer,
                "x-csrf-token": csrf,
                "Cookie": cookie_str,
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "same-origin",
                "Sec-Fetch-Dest": "empty",
                "Accept": "application/json",
            }

            # 2. Sign in
            sign_in_resp = client.post(
                f"{self._base_url}{_API_PREFIX}/sign-in",
                json={
                    "username": username,
                    "password": password,
                    "locale": "en",
                    "remember": False,
                },
                headers=api_headers,
            )
            sign_in_resp.raise_for_status()
            sign_in_data = sign_in_resp.json()

            # Update cookies from sign-in response
            for h_name, h_val in sign_in_resp.headers.multi_items():
                if h_name.lower() == "set-cookie":
                    parts = h_val.split(";")[0].split("=", 1)
                    if len(parts) == 2:
                        cookies[parts[0].strip()] = parts[1].strip()

            # 3. Consent
            ephemeral_token = sign_in_data.get("ephemeralToken")
            account_sub = sign_in_data["account"]["sub"]

            consent_headers = {
                **api_headers,
                "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
                "x-csrf-token": cookies.get("csrf-token", csrf),
            }
            if ephemeral_token:
                consent_headers["Authorization"] = f"Bearer {ephemeral_token}"

            consent_resp = client.post(
                f"{self._base_url}{_API_PREFIX}/consent",
                json={"sub": account_sub},
                headers=consent_headers,
            )
            consent_resp.raise_for_status()
            consent_data = consent_resp.json()

            # Extract code from the redirect URL
            redirect_url = consent_data["url"]
            parsed = urlparse(redirect_url)
            params = parse_qs(parsed.query)
            code = params["code"][0]
            return code

    # --- Token Exchange ---

    def token_exchange(self, code: str, pkce: PKCEChallenge) -> OAuthTokens:
        """Exchange an authorization code for tokens.

        Args:
            code: Authorization code from :meth:`authorize`.
            pkce: The same PKCE challenge used in the PAR.

        Returns:
            :class:`OAuthTokens` containing access/refresh tokens.
        """
        token_internal = self.metadata["token_endpoint"]
        token_ext = _rewrite_url(token_internal, self._base_url)

        resp, self._dpop_nonce = _dpop_aware_post(
            token_ext,
            self._dpop_key,
            token_internal,
            self._dpop_nonce,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "code_verifier": pkce.verifier,
            },
        )
        resp.raise_for_status()
        return OAuthTokens.from_response(resp.json())

    # --- Refresh ---

    def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Refresh tokens using a refresh token.

        Args:
            refresh_token: The refresh token from a previous token response.

        Returns:
            New :class:`OAuthTokens`.
        """
        token_internal = self.metadata["token_endpoint"]
        token_ext = _rewrite_url(token_internal, self._base_url)

        resp, self._dpop_nonce = _dpop_aware_post(
            token_ext,
            self._dpop_key,
            token_internal,
            self._dpop_nonce,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._client_id,
            },
        )
        resp.raise_for_status()
        return OAuthTokens.from_response(resp.json())

    # --- Revocation ---

    def revoke_token(self, token: str) -> None:
        """Revoke a token (access or refresh).

        Args:
            token: The token to revoke.
        """
        revocation_internal = self.metadata["revocation_endpoint"]
        revocation_ext = _rewrite_url(revocation_internal, self._base_url)

        resp, self._dpop_nonce = _dpop_aware_post(
            revocation_ext,
            self._dpop_key,
            revocation_internal,
            self._dpop_nonce,
            data={
                "token": token,
                "client_id": self._client_id,
            },
        )
        resp.raise_for_status()

    # --- Full Flow ---

    def authenticate(
        self, username: str, password: str, state: Optional[str] = None,
    ) -> OAuthTokens:
        """Run the full OAuth flow: PAR → sign-in → consent → token exchange.

        Args:
            username: Account handle (e.g. ``"alice.test"``).
            password: Account password.
            state: Optional OAuth state parameter.

        Returns:
            :class:`OAuthTokens` with DPoP-bound access and refresh tokens.
        """
        pkce = PKCEChallenge.generate()
        request_uri = self.pushed_authorization_request(
            pkce, state=state, login_hint=username,
        )
        code = self.authorize(request_uri, username, password)
        return self.token_exchange(code, pkce)

    # --- DPoP-Authenticated Requests ---

    def dpop_get(
        self, url: str, access_token: str, params: Optional[dict] = None,
    ) -> httpx.Response:
        """Make a DPoP-authenticated GET request.

        Args:
            url: The internal/issuer URL for the resource.
            access_token: The DPoP access token.
            params: Optional query parameters.

        Returns:
            The HTTP response.
        """
        ext_url = _rewrite_url(url, self._base_url)
        ath = DPoPKey.access_token_hash(access_token)
        proof = self._dpop_key.proof("GET", url, nonce=self._dpop_nonce, ath=ath)
        resp = httpx.get(
            ext_url,
            params=params,
            headers={
                "Authorization": f"DPoP {access_token}",
                "DPoP": proof,
            },
            timeout=10.0,
        )
        nonce = resp.headers.get("dpop-nonce")
        if nonce:
            self._dpop_nonce = nonce

        # Retry on nonce mismatch
        if resp.status_code == 401:
            body = resp.json()
            if body.get("error") == "use_dpop_nonce" and self._dpop_nonce:
                proof = self._dpop_key.proof(
                    "GET", url, nonce=self._dpop_nonce, ath=ath,
                )
                resp = httpx.get(
                    ext_url,
                    params=params,
                    headers={
                        "Authorization": f"DPoP {access_token}",
                        "DPoP": proof,
                    },
                    timeout=10.0,
                )
                nonce = resp.headers.get("dpop-nonce")
                if nonce:
                    self._dpop_nonce = nonce

        return resp

    def dpop_post(
        self,
        url: str,
        access_token: str,
        json: Optional[dict] = None,
        content: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> httpx.Response:
        """Make a DPoP-authenticated POST request.

        Args:
            url: The internal/issuer URL for the resource.
            access_token: The DPoP access token.
            json: Optional JSON body.
            content: Optional raw body bytes.
            content_type: Content type for raw body.

        Returns:
            The HTTP response.
        """
        ext_url = _rewrite_url(url, self._base_url)
        ath = DPoPKey.access_token_hash(access_token)
        proof = self._dpop_key.proof("POST", url, nonce=self._dpop_nonce, ath=ath)
        headers: dict[str, str] = {
            "Authorization": f"DPoP {access_token}",
            "DPoP": proof,
        }

        kwargs: dict = {"headers": headers, "timeout": 10.0}
        if content is not None:
            headers["Content-Type"] = content_type or "application/octet-stream"
            kwargs["content"] = content
        else:
            kwargs["json"] = json

        resp = httpx.post(ext_url, **kwargs)
        nonce = resp.headers.get("dpop-nonce")
        if nonce:
            self._dpop_nonce = nonce

        # Retry on nonce mismatch
        if resp.status_code in (400, 401):
            try:
                body = resp.json()
            except Exception:
                return resp
            if body.get("error") == "use_dpop_nonce" and self._dpop_nonce:
                proof = self._dpop_key.proof(
                    "POST", url, nonce=self._dpop_nonce, ath=ath,
                )
                headers["DPoP"] = proof
                resp = httpx.post(ext_url, **kwargs)
                nonce = resp.headers.get("dpop-nonce")
                if nonce:
                    self._dpop_nonce = nonce

        return resp

    def xrpc_get(
        self, method: str, access_token: str, params: Optional[dict] = None,
    ) -> dict:
        """DPoP-authenticated XRPC query.

        Args:
            method: XRPC method name (e.g. ``"com.atproto.repo.describeRepo"``).
            access_token: The DPoP access token.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        url = f"{self.issuer}/xrpc/{method}"
        resp = self.dpop_get(url, access_token, params=params)
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    def xrpc_post(
        self,
        method: str,
        access_token: str,
        data: Optional[dict] = None,
        *,
        content: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> dict:
        """DPoP-authenticated XRPC procedure.

        Args:
            method: XRPC method name.
            access_token: The DPoP access token.
            data: JSON body.
            content: Raw body bytes (for blob uploads).
            content_type: Content type for raw body.

        Returns:
            Parsed JSON response.
        """
        url = f"{self.issuer}/xrpc/{method}"
        resp = self.dpop_post(
            url, access_token, json=data, content=content, content_type=content_type,
        )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()
