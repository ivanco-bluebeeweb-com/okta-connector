"""Okta Connector -- App settings panel."""
from __future__ import annotations

from imperal_sdk import ui

import handlers as h
from app import ext


@ext.panel("okta_settings", slot="center", title="Okta settings", icon="Settings", center_overlay=True)
async def okta_settings(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Text("No Okta org connected yet.", variant="body")
    rows = []
    for c in connections:
        rows.append(ui.Stack(direction="h", gap=2, align="center", children=[
            ui.Text(f"{c.get('label') or c.get('org_domain', '')} ({c.get('auth_mode', 'api_token')})", variant="body"),
            ui.Button("Disconnect", variant="destructive", on_click=ui.Call("disconnect_okta", {"connection_id": c.get("id", "")})),
        ]))
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="Connected orgs", level=2),
        *rows,
    ])
