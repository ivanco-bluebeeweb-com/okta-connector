"""Okta Connector panels.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as ServiceNow
Connector's / AWS Connector's panels.py). Every section is a plain
ui.Stack, stacked vertically and left-aligned, no Card border/background/
shadow. Disconnect lives only in "App settings" (panels_settings.py). The
one secondary "App settings" button is always the LAST element at the
bottom of the sidebar.

Per Vlad's standing rule: every input carries its own label (not just a
placeholder), placeholders are contextually specific, the form container
is stretched to the full width of the left sidebar with its contents
stretched to fill it, and the sidebar carries NO instructions that
duplicate the "How do I set this up?" modal.
"""
from __future__ import annotations

from imperal_sdk import ui

import handlers as h
from app import ext


def _field(label: str, node: ui.UINode) -> ui.UINode:
    return ui.Stack(direction="v", gap=1, align="stretch", children=[
        ui.Text(label, variant="caption"),
        node,
    ])


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="Settings", on_click=ui.Call("__panel__okta_settings"),
    )


@ext.panel("okta_sidebar", slot="left", title="Okta")
async def okta_sidebar(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Stack(direction="v", gap=3, align="stretch", children=[
            ui.Button("How do I get this?", variant="ghost", size="sm", icon="HelpCircle",
                      on_click=ui.Call("__panel__okta_connect_help")),
            ui.Form(action="connect_okta", submit_label="Connect", children=[
                _field("Org label", ui.Input(param_name="label", placeholder="Acme Production")),
                _field("Org domain", ui.Input(param_name="org_domain", placeholder="acme.okta.com")),
                _field("Auth mode", ui.Select(param_name="auth_mode", options=["api_token", "oauth2_service_app"], value="api_token")),
                _field("API token", ui.Password(param_name="api_token", placeholder="SSWS API token from Security > API > Tokens")),
                _field("Service App client ID (if OAuth2)", ui.Input(param_name="client_id", placeholder="0oa1b2c3d4e5f6g7h8i9")),
                _field("Service App private key (if OAuth2)", ui.Password(param_name="private_key", placeholder="-----BEGIN PRIVATE KEY-----")),
            ]),
        ])
    c = connections[0]
    return ui.Stack(direction="v", gap=1, align="stretch", children=[
        ui.Text(c.get("label") or c.get("org_domain", ""), variant="subtitle"),
        ui.Divider(),
        ui.Button("Users", variant="ghost", full_width=True, icon="Users", on_click=ui.Call("__panel__okta_users")),
        ui.Button("Groups", variant="ghost", full_width=True, icon="UsersRound", on_click=ui.Call("__panel__okta_groups")),
        ui.Button("Applications", variant="ghost", full_width=True, icon="Grid", on_click=ui.Call("__panel__okta_apps")),
        ui.Button("Policies", variant="ghost", full_width=True, icon="ShieldCheck", on_click=ui.Call("__panel__okta_policies")),
        ui.Button("System Log", variant="ghost", full_width=True, icon="ScrollText", on_click=ui.Call("__panel__okta_system_log")),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("okta_connect_help", slot="center", title="Connect Okta", center_overlay=True)
async def okta_connect_help(ctx, **kwargs) -> ui.UINode:
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="How to connect Okta", level=2),
        ui.Markdown(text=(
            "**API Token (simplest):**\n"
            "1. In Okta Admin Console go to *Security > API > Tokens*.\n"
            "2. Click *Create Token*, name it, copy the value immediately (shown once).\n"
            "3. Paste it above as the API token.\n\n"
            "**OAuth2 Service App (recommended for production):**\n"
            "1. Go to *Applications > Applications > Create App Integration*.\n"
            "2. Choose *API Services*.\n"
            "3. Under *General*, generate a public/private key pair (or upload your own) -- "
            "copy the **private key** above.\n"
            "4. Grant these scopes under *Okta API Scopes*: `okta.users.manage`, "
            "`okta.groups.manage`, `okta.apps.manage`, `okta.logs.read`, "
            "`okta.factors.manage`, `okta.roles.manage`, `okta.sessions.manage`.\n"
            "5. Copy the *Client ID* above."
        )),
    ])


@ext.panel("okta_center", slot="center", title="Okta")
async def okta_center(ctx, **kwargs) -> ui.UINode:
    return ui.Empty(message="Nothing to show here", icon="Fingerprint")
