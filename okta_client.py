"""Thin Okta Management API + System Log API REST client.

Supports both SSWS API Token and OAuth2 Service App (client credentials with
a private-key JWT assertion) auth modes, since Okta orgs commonly use either
depending on how the integration was set up.
"""
from __future__ import annotations

import time
from typing import Any

import httpx


class OktaError(RuntimeError):
    """A safe provider-facing error; never includes credentials."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class OktaClient:
    """REST client for the Okta Management API (/api/v1) and System Log (/api/v1/logs)."""

    def __init__(
        self,
        org_domain: str,
        auth_mode: str = "api_token",
        api_token: str = "",
        client_id: str = "",
        private_key: str = "",
        oauth_scopes: str = "",
        *,
        timeout: float = 30.0,
    ):
        domain = (org_domain or "").strip()
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
        if not domain:
            raise OktaError("Org domain is required, e.g. 'acme.okta.com'.")
        self.base_url = f"https://{domain}"
        self.auth_mode = auth_mode
        self.api_token = api_token or ""
        self.client_id = client_id or ""
        self.private_key = private_key or ""
        self.oauth_scopes = oauth_scopes or "okta.users.manage okta.groups.manage okta.apps.manage okta.logs.read okta.factors.manage okta.roles.manage okta.sessions.manage"
        self.timeout = timeout
        self._token: str | None = None
        self._token_expiry: float = 0.0

    async def _get_oauth_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 30:
            return self._token
        import uuid

        try:
            import jwt as pyjwt
        except ImportError as exc:
            raise OktaError("OAuth2 Service App mode requires PyJWT to be installed.") from exc

        now = int(time.time())
        token_endpoint = f"{self.base_url}/oauth2/v1/token"
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": token_endpoint,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        }
        try:
            assertion = pyjwt.encode(claims, self.private_key, algorithm="RS256")
        except Exception as exc:
            raise OktaError(f"Failed to sign OAuth2 client assertion: {exc}") from exc

        data = {
            "grant_type": "client_credentials",
            "scope": self.oauth_scopes,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(token_endpoint, data=data)
        if resp.status_code >= 400:
            raise OktaError(f"OAuth2 token exchange failed ({resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        self._token = payload.get("access_token", "")
        self._token_expiry = time.time() + int(payload.get("expires_in", 3600))
        if not self._token:
            raise OktaError("OAuth2 token exchange returned no access_token.")
        return self._token

    async def _headers(self) -> dict:
        if self.auth_mode == "oauth2_service_app":
            token = await self._get_oauth_token()
            return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        return {"Authorization": f"SSWS {self.api_token}", "Accept": "application/json", "Content-Type": "application/json"}

    async def request(self, method: str, path: str, *, params: dict | None = None, json_body: Any = None, full_url: str = "") -> tuple[Any, dict]:
        """Return (parsed_json_or_none, response_headers). Raises OktaError on failure."""
        url = full_url or f"{self.base_url}{path}"
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(method, url, headers=headers, params=params, json=json_body)
        if resp.status_code == 429:
            reset = resp.headers.get("X-Rate-Limit-Reset", "")
            raise OktaError(f"Okta rate limit hit; resets at {reset}.", retryable=True)
        if resp.status_code >= 400:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("errorSummary") or body.get("error_description") or resp.text[:300]
            except Exception:
                detail = resp.text[:300]
            raise OktaError(f"Okta API error ({resp.status_code}): {detail}")
        if resp.status_code == 204 or not resp.content:
            return None, dict(resp.headers)
        return resp.json(), dict(resp.headers)

    async def verify_connection(self) -> dict:
        """Cheap call used by connect_okta to prove the domain+credentials actually work."""
        data, _ = await self.request("GET", "/api/v1/users/me")
        return data or {}


def parse_next_link(headers: dict) -> str:
    """Extract the 'next' cursor URL from an Okta Link response header, if present."""
    link = headers.get("Link") or headers.get("link") or ""
    if not link:
        return ""
    for part in link.split(","):
        if 'rel="next"' in part:
            start = part.find("<")
            end = part.find(">")
            if start != -1 and end != -1:
                return part[start + 1:end]
    return ""
