"""Okta Connector -- center panels for Users/Groups/Applications/Policies/System Log."""
from __future__ import annotations

from imperal_sdk import ui

import handlers as h
from app import ext


@ext.panel("okta_users", slot="center", title="Users", center_overlay=True)
async def okta_users(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(message="Nothing to show here", icon="Users")
    c = connections[0]
    client = h._client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/users", params={"limit": 50})
    except Exception as exc:  # noqa: BLE001
        return ui.Alert(type="error", message=f"Could not load users: {exc}")
    rows = []
    for u in (data or []):
        profile = u.get("profile", {}) or {}
        rows.append({
            "name": f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
            "email": profile.get("email", ""),
            "status": u.get("status", ""),
        })
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="Users", level=2),
        ui.DataTable(
            rows=rows,
            columns=[
                ui.DataColumn(key="name", label="Name"),
                ui.DataColumn(key="email", label="Email"),
                ui.DataColumn(key="status", label="Status"),
            ],
        ) if rows else ui.Empty(message="No users found", icon="Users"),
    ])


@ext.panel("okta_groups", slot="center", title="Groups", center_overlay=True)
async def okta_groups(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(message="Nothing to show here", icon="UsersRound")
    c = connections[0]
    client = h._client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/groups", params={"limit": 50})
    except Exception as exc:  # noqa: BLE001
        return ui.Alert(type="error", message=f"Could not load groups: {exc}")
    rows = []
    for g in (data or []):
        profile = g.get("profile", {}) or {}
        rows.append({"name": profile.get("name", ""), "description": profile.get("description", ""), "type": g.get("type", "")})
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="Groups", level=2),
        ui.DataTable(
            rows=rows,
            columns=[
                ui.DataColumn(key="name", label="Name"),
                ui.DataColumn(key="description", label="Description"),
                ui.DataColumn(key="type", label="Type"),
            ],
        ) if rows else ui.Empty(message="No groups found", icon="UsersRound"),
    ])


@ext.panel("okta_apps", slot="center", title="Applications", center_overlay=True)
async def okta_apps(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(message="Nothing to show here", icon="Grid")
    c = connections[0]
    client = h._client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/apps", params={"limit": 50})
    except Exception as exc:  # noqa: BLE001
        return ui.Alert(type="error", message=f"Could not load applications: {exc}")
    rows = [{"label": a.get("label", ""), "status": a.get("status", ""), "sign_on_mode": a.get("signOnMode", "")} for a in (data or [])]
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="Applications", level=2),
        ui.DataTable(
            rows=rows,
            columns=[
                ui.DataColumn(key="label", label="Application"),
                ui.DataColumn(key="status", label="Status"),
                ui.DataColumn(key="sign_on_mode", label="Sign-on mode"),
            ],
        ) if rows else ui.Empty(message="No applications found", icon="Grid"),
    ])


@ext.panel("okta_policies", slot="center", title="Policies", center_overlay=True)
async def okta_policies(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(message="Nothing to show here", icon="ShieldCheck")
    c = connections[0]
    client = h._client_for(c)
    rows = []
    for ptype in ("OKTA_SIGN_ON", "PASSWORD", "MFA_ENROLL"):
        try:
            data, _ = await client.request("GET", "/api/v1/policies", params={"type": ptype})
        except Exception:  # noqa: BLE001
            continue
        for p in (data or []):
            rows.append({"name": p.get("name", ""), "type": p.get("type", ""), "status": p.get("status", "")})
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="Policies", level=2),
        ui.DataTable(
            rows=rows,
            columns=[
                ui.DataColumn(key="name", label="Name"),
                ui.DataColumn(key="type", label="Type"),
                ui.DataColumn(key="status", label="Status"),
            ],
        ) if rows else ui.Empty(message="No policies found", icon="ShieldCheck"),
    ])


@ext.panel("okta_system_log", slot="center", title="System Log", center_overlay=True)
async def okta_system_log(ctx, **kwargs) -> ui.UINode:
    connections = await h._load_connections(ctx)
    if not connections:
        return ui.Empty(message="Nothing to show here", icon="ScrollText")
    c = connections[0]
    client = h._client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/logs", params={"limit": 50})
    except Exception as exc:  # noqa: BLE001
        return ui.Alert(type="error", message=f"Could not load system log: {exc}")
    rows = []
    for e in (data or []):
        actor = e.get("actor", {}) or {}
        outcome = e.get("outcome", {}) or {}
        rows.append({
            "time": e.get("published", ""),
            "event_type": e.get("eventType", ""),
            "actor": actor.get("displayName", ""),
            "result": outcome.get("result", ""),
        })
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Header(text="System Log", level=2),
        ui.DataTable(
            rows=rows,
            columns=[
                ui.DataColumn(key="time", label="Time"),
                ui.DataColumn(key="event_type", label="Event"),
                ui.DataColumn(key="actor", label="Actor"),
                ui.DataColumn(key="result", label="Result"),
            ],
        ) if rows else ui.Empty(message="No events found", icon="ScrollText"),
    ])
