"""Okta Connector extension declaration.

Okta is a cloud identity provider (IdP): SSO, MFA, lifecycle management, and
API Access Management, exposed through the Okta Management API (/api/v1/*)
plus a separate System Log API for audit/security event streaming.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "okta-connector",
    version="0.1.0",
    display_name="Okta",
    description=(
        "Connect your own Okta org (API Token or OAuth2 Service App) to manage "
        "Users, Groups, Applications, MFA Factors, Policies, admin Roles and "
        "Sessions, plus stream the System Log for security/audit visibility."
    ),
    icon="icon.svg",
    capabilities=["okta:read", "okta:write"],
    actions_explicit=True,
    system=False,
)

chat = ChatExtension(
    ext,
    tool_name="okta",
    description=(
        "Okta Connector — manage Users, Groups, Applications, MFA Factors, "
        "Policies, admin Roles, Sessions, and the System Log for an Okta org."
    ),
)

ext.secret(
    "okta_connections",
    "JSON list of connected Okta orgs and encrypted credentials. Managed only through connect_okta and disconnect_okta.",
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=90,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Report whether at least one Okta org connection is saved."""
    import json

    raw = await ctx.secrets.get("okta_connections")
    connections = []
    if raw:
        try:
            connections = json.loads(raw)
        except (TypeError, ValueError):
            connections = []
    if not isinstance(connections, list) or not connections:
        return {"status": "not_connected", "detail": "No Okta org connected yet."}
    return {"status": "ok", "detail": f"{len(connections)} Okta org(s) connected."}
