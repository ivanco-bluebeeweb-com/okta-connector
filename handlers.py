"""Chat functions for Okta Connector (Okta Management API + System Log API)."""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import okta_client as oc
from app import chat
from schemas import (
    AdminRole, AppIdParams, AppList, AssignGroupToAppParams, AssignRoleParams,
    AssignUserToAppParams, ConnectOktaParams, ConnectionList, ConnectionRefParams,
    CreateGroupParams, CreateUserParams, DeleteResult, DisconnectOktaParams,
    FactorList, GroupIdParams, GroupList, GroupMemberParams, HealthAudit,
    ListAppsParams, ListFactorsParams, ListGroupsParams, ListPoliciesParams,
    ListSystemLogParams, ListUsersParams, NoParams, OktaApp, OktaConnection,
    OktaFactor, OktaGroup, OktaPolicy, OktaUser, PolicyList, RemoveRoleParams,
    RoleList, SystemLogEvent, SystemLogList, UpdateUserParams, UserIdParams,
    UserList,
)

_SECRET_NAME = "okta_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


def _connection_entity(c: dict) -> OktaConnection:
    return OktaConnection(
        connection_id=c.get("id", ""),
        label=c.get("label") or c.get("org_domain", ""),
        org_domain=c.get("org_domain", ""),
        auth_mode=c.get("auth_mode", "api_token"),
    )


async def _resolve_connection(ctx, connection_id: str = "") -> dict:
    connections = await _load_connections(ctx)
    if not connections:
        raise ValueError("No Okta org connected yet. Use connect_okta first.")
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        raise ValueError(f"No saved Okta connection with id '{connection_id}'.")
    return connections[0]


def _client_for(c: dict) -> oc.OktaClient:
    return oc.OktaClient(
        org_domain=c.get("org_domain", ""),
        auth_mode=c.get("auth_mode", "api_token"),
        api_token=c.get("api_token", ""),
        client_id=c.get("client_id", ""),
        private_key=c.get("private_key", ""),
    )


@chat.tool(action_type="write", effects=["okta.provider.connected"])
async def connect_okta(ctx, params: ConnectOktaParams) -> ActionResult[OktaConnection]:
    """Connect an Okta org via API Token or OAuth2 Service App, after verifying connectivity."""
    if params.auth_mode == "oauth2_service_app" and not (params.client_id and params.private_key):
        return ActionResult.fail("client_id and private_key are required for oauth2_service_app mode.")
    if params.auth_mode == "api_token" and not params.api_token:
        return ActionResult.fail("api_token is required for api_token mode.")
    client = oc.OktaClient(
        org_domain=params.org_domain,
        auth_mode=params.auth_mode,
        api_token=params.api_token,
        client_id=params.client_id,
        private_key=params.private_key,
    )
    try:
        await client.verify_connection()
    except oc.OktaError as exc:
        return ActionResult.fail(f"Could not verify Okta connection: {exc}")
    connections = await _load_connections(ctx)
    entry = {
        "id": str(uuid.uuid4()),
        "label": params.label or params.org_domain,
        "org_domain": client.base_url.replace("https://", ""),
        "auth_mode": params.auth_mode,
        "api_token": params.api_token,
        "client_id": params.client_id,
        "private_key": params.private_key,
    }
    connections.append(entry)
    await _save_connections(ctx, connections)
    return ActionResult.ok(_connection_entity(entry))


@chat.tool(action_type="write", effects=["okta.provider.disconnected"])
async def disconnect_okta(ctx, params: DisconnectOktaParams) -> ActionResult[DeleteResult]:
    """Disconnect an Okta org: deletes the saved token/credentials. Nothing in Okta itself is changed."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.fail(f"No saved Okta connection with id '{params.connection_id}'.")
    await _save_connections(ctx, remaining)
    return ActionResult.ok(DeleteResult(ok=True, detail="Okta org disconnected."))


@chat.tool(action_type="read")
async def list_connections(ctx, params: NoParams) -> ActionResult[ConnectionList]:
    """List the connected Okta orgs."""
    connections = await _load_connections(ctx)
    return ActionResult.ok(ConnectionList(connections=[_connection_entity(c) for c in connections]))


def _user_entity(u: dict) -> OktaUser:
    profile = u.get("profile", {}) or {}
    return OktaUser(
        user_id=u.get("id", ""),
        login=profile.get("login", ""),
        email=profile.get("email", ""),
        first_name=profile.get("firstName", ""),
        last_name=profile.get("lastName", ""),
        status=u.get("status", ""),
        created=u.get("created", ""),
    )


@chat.tool(action_type="read")
async def list_users(ctx, params: ListUsersParams) -> ActionResult[UserList]:
    """List Okta users, optionally filtered by status or search text."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 200))}
    filters = []
    if params.status_filter:
        filters.append(f'status eq "{params.status_filter}"')
    if filters:
        q["filter"] = " and ".join(filters)
    if params.q:
        q["q"] = params.q
    try:
        data, _ = await client.request("GET", "/api/v1/users", params=q)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(UserList(users=[_user_entity(u) for u in (data or [])]))


@chat.tool(action_type="read")
async def get_user(ctx, params: UserIdParams) -> ActionResult[OktaUser]:
    """Read one Okta user in full by id or login."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_user_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.user.created"])
async def create_user(ctx, params: CreateUserParams) -> ActionResult[OktaUser]:
    """Create a new Okta user with profile fields, optionally activating them immediately."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    login = params.login or params.email
    body = {
        "profile": {
            "firstName": params.first_name,
            "lastName": params.last_name,
            "email": params.email,
            "login": login,
        }
    }
    try:
        data, _ = await client.request("POST", "/api/v1/users", params={"activate": str(params.activate).lower()}, json_body=body)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_user_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.user.updated"])
async def update_user(ctx, params: UpdateUserParams) -> ActionResult[OktaUser]:
    """Update selected profile fields of an existing Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    profile: dict = {}
    if params.first_name:
        profile["firstName"] = params.first_name
    if params.last_name:
        profile["lastName"] = params.last_name
    if params.email:
        profile["email"] = params.email
    try:
        data, _ = await client.request("POST", f"/api/v1/users/{params.user_id}", json_body={"profile": profile})
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_user_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.user.status_changed"])
async def activate_user(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Activate a STAGED Okta user (sends activation email unless password already set)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/activate", params={"sendEmail": "true"})
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User activated."))


@chat.tool(action_type="write", effects=["okta.user.status_changed"])
async def suspend_user(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Suspend an active Okta user, blocking their sign-in."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/suspend")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User suspended."))


@chat.tool(action_type="write", effects=["okta.user.status_changed"])
async def unsuspend_user(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Unsuspend a suspended Okta user, restoring their sign-in access."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/unsuspend")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User unsuspended."))


@chat.tool(action_type="write", effects=["okta.user.status_changed"])
async def deactivate_user(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Deactivate (soft-delete) an Okta user. Okta keeps a 30-day recovery window internally."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/deactivate")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User deactivated."))


@chat.tool(action_type="write", effects=["okta.user.unlocked"])
async def unlock_user(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Unlock a locked-out Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/unlock")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User unlocked."))


@chat.tool(action_type="write", effects=["okta.user.password_expired"])
async def expire_user_password(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Expire an Okta user's password, forcing them to set a new one at next login."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/expire_password")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="Password expired; user must set a new one at next login."))


def _group_entity(g: dict) -> OktaGroup:
    profile = g.get("profile", {}) or {}
    return OktaGroup(
        group_id=g.get("id", ""),
        name=profile.get("name", ""),
        description=profile.get("description", ""),
        group_type=g.get("type", ""),
    )


@chat.tool(action_type="read")
async def list_groups(ctx, params: ListGroupsParams) -> ActionResult[GroupList]:
    """List Okta groups, optionally filtered by search text."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 200))}
    if params.q:
        q["q"] = params.q
    try:
        data, _ = await client.request("GET", "/api/v1/groups", params=q)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(GroupList(groups=[_group_entity(g) for g in (data or [])]))


@chat.tool(action_type="read")
async def get_group(ctx, params: GroupIdParams) -> ActionResult[OktaGroup]:
    """Read one Okta group in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/groups/{params.group_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_group_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.group.created"])
async def create_group(ctx, params: CreateGroupParams) -> ActionResult[OktaGroup]:
    """Create a new Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    body = {"profile": {"name": params.name, "description": params.description}}
    try:
        data, _ = await client.request("POST", "/api/v1/groups", json_body=body)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_group_entity(data or {}))


@chat.tool(action_type="read")
async def list_group_members(ctx, params: GroupIdParams) -> ActionResult[UserList]:
    """List the members of an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/groups/{params.group_id}/users")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(UserList(users=[_user_entity(u) for u in (data or [])]))


@chat.tool(action_type="write", effects=["okta.group.member_added"])
async def add_user_to_group(ctx, params: GroupMemberParams) -> ActionResult[DeleteResult]:
    """Add a user to an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("PUT", f"/api/v1/groups/{params.group_id}/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User added to group."))


@chat.tool(action_type="write", effects=["okta.group.member_removed"])
async def remove_user_from_group(ctx, params: GroupMemberParams) -> ActionResult[DeleteResult]:
    """Remove a user from an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("DELETE", f"/api/v1/groups/{params.group_id}/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User removed from group."))


def _app_entity(a: dict) -> OktaApp:
    return OktaApp(
        app_id=a.get("id", ""),
        label=a.get("label", ""),
        status=a.get("status", ""),
        sign_on_mode=a.get("signOnMode", ""),
    )


@chat.tool(action_type="read")
async def list_apps(ctx, params: ListAppsParams) -> ActionResult[AppList]:
    """List Okta applications, optionally filtered by search text."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 200))}
    if params.q:
        q["q"] = params.q
    try:
        data, _ = await client.request("GET", "/api/v1/apps", params=q)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(AppList(apps=[_app_entity(a) for a in (data or [])]))


@chat.tool(action_type="read")
async def get_app(ctx, params: AppIdParams) -> ActionResult[OktaApp]:
    """Read one Okta application in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/apps/{params.app_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_app_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.app.user_assigned"])
async def assign_user_to_app(ctx, params: AssignUserToAppParams) -> ActionResult[DeleteResult]:
    """Assign an Okta user directly to an application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request(
            "POST", f"/api/v1/apps/{params.app_id}/users",
            json_body={"id": params.user_id, "scope": "USER"},
        )
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="User assigned to application."))


@chat.tool(action_type="write", effects=["okta.app.group_assigned"])
async def assign_group_to_app(ctx, params: AssignGroupToAppParams) -> ActionResult[DeleteResult]:
    """Assign an Okta group to an application (all group members get access)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("PUT", f"/api/v1/apps/{params.app_id}/groups/{params.group_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="Group assigned to application."))


@chat.tool(action_type="write", effects=["okta.app.status_changed"])
async def activate_app(ctx, params: AppIdParams) -> ActionResult[DeleteResult]:
    """Activate an Okta application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/apps/{params.app_id}/lifecycle/activate")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="Application activated."))


@chat.tool(action_type="write", effects=["okta.app.status_changed"])
async def deactivate_app(ctx, params: AppIdParams) -> ActionResult[DeleteResult]:
    """Deactivate an Okta application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/apps/{params.app_id}/lifecycle/deactivate")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="Application deactivated."))


def _factor_entity(f: dict) -> OktaFactor:
    return OktaFactor(
        factor_id=f.get("id", ""),
        factor_type=f.get("factorType", ""),
        provider=f.get("provider", ""),
        status=f.get("status", ""),
    )


@chat.tool(action_type="read")
async def list_user_factors(ctx, params: ListFactorsParams) -> ActionResult[FactorList]:
    """List MFA factors enrolled for an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}/factors")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(FactorList(factors=[_factor_entity(f) for f in (data or [])]))


@chat.tool(action_type="write", effects=["okta.user.factor_reset"])
async def reset_user_factors(ctx, params: UserIdParams) -> ActionResult[DeleteResult]:
    """Reset ALL enrolled MFA factors for an Okta user -- they must re-enroll at next login. Use when a user has lost their MFA device."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/reset_factors")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="All MFA factors reset; user must re-enroll at next login."))


def _policy_entity(p: dict) -> OktaPolicy:
    return OktaPolicy(
        policy_id=p.get("id", ""),
        name=p.get("name", ""),
        policy_type=p.get("type", ""),
        status=p.get("status", ""),
    )


@chat.tool(action_type="read")
async def list_policies(ctx, params: ListPoliciesParams) -> ActionResult[PolicyList]:
    """List Okta policies of a given type (sign-on, password, MFA enrollment, access)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/policies", params={"type": params.policy_type})
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(PolicyList(policies=[_policy_entity(p) for p in (data or [])]))


@chat.tool(action_type="read")
async def get_policy(ctx, params: PolicyIdParams) -> ActionResult[OktaPolicy]:
    """Read one Okta policy in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/policies/{params.policy_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_policy_entity(data or {}))


def _role_entity(r: dict) -> AdminRole:
    return AdminRole(
        role_id=r.get("id", ""),
        role_type=r.get("type", ""),
        status=r.get("status", ""),
    )


@chat.tool(action_type="read")
async def list_admin_roles(ctx, params: ListAdminRolesParams) -> ActionResult[RoleList]:
    """List admin roles assigned to an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}/roles")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(RoleList(roles=[_role_entity(r) for r in (data or [])]))


@chat.tool(action_type="write", effects=["okta.role.assigned"])
async def assign_admin_role(ctx, params: AssignRoleParams) -> ActionResult[AdminRole]:
    """Assign an admin role to an Okta user (e.g. SUPER_ADMIN, ORG_ADMIN, APP_ADMIN)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request(
            "POST", f"/api/v1/users/{params.user_id}/roles",
            json_body={"type": params.role_type},
        )
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(_role_entity(data or {}))


@chat.tool(action_type="write", effects=["okta.role.removed"])
async def remove_admin_role(ctx, params: RemoveRoleParams) -> ActionResult[DeleteResult]:
    """Remove an admin role assignment from an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("DELETE", f"/api/v1/users/{params.user_id}/roles/{params.role_id}")
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(DeleteResult(ok=True, detail="Admin role removed."))


def _log_entity(e: dict) -> SystemLogEvent:
    actor = e.get("actor", {}) or {}
    outcome = e.get("outcome", {}) or {}
    return SystemLogEvent(
        uuid=e.get("uuid", ""),
        published=e.get("published", ""),
        event_type=e.get("eventType", ""),
        actor=actor.get("displayName", "") or actor.get("alternateId", ""),
        outcome_result=outcome.get("result", ""),
        outcome_reason=outcome.get("reason", ""),
    )


@chat.tool(action_type="read")
async def list_system_log(ctx, params: ListSystemLogParams) -> ActionResult[SystemLogList]:
    """List Okta System Log events (audit trail of logins, MFA, admin actions), optionally filtered by time range or SCIM-style filter expression."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 1000))}
    if params.since:
        q["since"] = params.since
    if params.until:
        q["until"] = params.until
    if params.filter_expr:
        q["filter"] = params.filter_expr
    if params.q:
        q["q"] = params.q
    try:
        data, headers = await client.request("GET", "/api/v1/logs", params=q)
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    next_cursor = oc.parse_next_link(headers)
    return ActionResult.ok(SystemLogList(events=[_log_entity(e) for e in (data or [])], next_cursor=next_cursor))


@chat.tool(action_type="read")
async def audit_org(ctx, params: ConnectionRefParams) -> ActionResult[HealthAudit]:
    """Build one aggregated health report for the connected Okta org: active/suspended user counts, admin count, and recent failed logins."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        suspended, _ = await client.request("GET", "/api/v1/users", params={"filter": 'status eq "SUSPENDED"', "limit": 200})
        active, _ = await client.request("GET", "/api/v1/users", params={"filter": 'status eq "ACTIVE"', "limit": 200})
        failed, _ = await client.request(
            "GET", "/api/v1/logs",
            params={"filter": 'eventType eq "user.session.start" and outcome.result eq "FAILURE"', "limit": 50},
        )
    except oc.OktaError as exc:
        return ActionResult.fail(str(exc))
    return ActionResult.ok(HealthAudit(
        org_domain=c.get("org_domain", ""),
        active_users=len(active or []),
        suspended_users=len(suspended or []),
        admin_count=0,
        failed_logins_24h=len(failed or []),
        notes=(
            f"{len(active or [])} active users, {len(suspended or [])} suspended, "
            f"{len(failed or [])} failed logins in the sampled window. "
            "Admin count requires per-user role lookups (use list_admin_roles)."
        ),
    ))
