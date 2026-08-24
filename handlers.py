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


@chat.function("connect_okta", "Connect an Okta org via API Token or OAuth2 Service App, after verifying connectivity.", action_type="write", chain_callable=True, data_model=OktaConnection, event="okta-connector.connect_okta", effects=["okta.provider.connected"])
async def connect_okta(ctx, params: ConnectOktaParams) -> ActionResult:
    """Connect an Okta org via API Token or OAuth2 Service App, after verifying connectivity."""
    if params.auth_mode == "oauth2_service_app" and not (params.client_id and params.private_key):
        return ActionResult.error("client_id and private_key are required for oauth2_service_app mode.")
    if params.auth_mode == "api_token" and not params.api_token:
        return ActionResult.error("api_token is required for api_token mode.")
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
        return ActionResult.error(f"Could not verify Okta connection: {exc}")
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
    return ActionResult.success(data=_connection_entity(entry))


@chat.function("disconnect_okta", "Disconnect an Okta org: deletes the saved token/credentials. Nothing in Okta itself is changed.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.disconnect_okta", effects=["okta.provider.disconnected"])
async def disconnect_okta(ctx, params: DisconnectOktaParams) -> ActionResult:
    """Disconnect an Okta org: deletes the saved token/credentials. Nothing in Okta itself is changed."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error(f"No saved Okta connection with id '{params.connection_id}'.")
    await _save_connections(ctx, remaining)
    return ActionResult.success(data=DeleteResult(ok=True, detail="Okta org disconnected."))


@chat.function("list_connections", "List the connected Okta orgs.", action_type="read", chain_callable=True, data_model=ConnectionList, event="okta-connector.list_connections")
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List the connected Okta orgs."""
    connections = await _load_connections(ctx)
    return ActionResult.success(data=ConnectionList(connections=[_connection_entity(c) for c in connections]))


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


@chat.function("list_users", "List Okta users, optionally filtered by status or search text.", action_type="read", chain_callable=True, data_model=UserList, event="okta-connector.list_users")
async def list_users(ctx, params: ListUsersParams) -> ActionResult:
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
        return ActionResult.error(str(exc))
    return ActionResult.success(data=UserList(users=[_user_entity(u) for u in (data or [])]))


@chat.function("get_user", "Read one Okta user in full by id or login.", action_type="read", chain_callable=True, data_model=OktaUser, event="okta-connector.get_user")
async def get_user(ctx, params: UserIdParams) -> ActionResult:
    """Read one Okta user in full by id or login."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_user_entity(data or {}))


@chat.function("create_user", "Create a new Okta user with profile fields, optionally activating them immediately.", action_type="write", chain_callable=True, data_model=OktaUser, event="okta-connector.create_user", effects=["okta.user.created"])
async def create_user(ctx, params: CreateUserParams) -> ActionResult:
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
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_user_entity(data or {}))


@chat.function("update_user", "Update selected profile fields of an existing Okta user.", action_type="write", chain_callable=True, data_model=OktaUser, event="okta-connector.update_user", effects=["okta.user.updated"])
async def update_user(ctx, params: UpdateUserParams) -> ActionResult:
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
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_user_entity(data or {}))


@chat.function("activate_user", "Activate a STAGED Okta user (sends activation email unless password already set).", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.activate_user", effects=["okta.user.status_changed"])
async def activate_user(ctx, params: UserIdParams) -> ActionResult:
    """Activate a STAGED Okta user (sends activation email unless password already set)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/activate", params={"sendEmail": "true"})
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User activated."))


@chat.function("suspend_user", "Suspend an active Okta user, blocking their sign-in.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.suspend_user", effects=["okta.user.status_changed"])
async def suspend_user(ctx, params: UserIdParams) -> ActionResult:
    """Suspend an active Okta user, blocking their sign-in."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/suspend")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User suspended."))


@chat.function("unsuspend_user", "Unsuspend a suspended Okta user, restoring their sign-in access.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.unsuspend_user", effects=["okta.user.status_changed"])
async def unsuspend_user(ctx, params: UserIdParams) -> ActionResult:
    """Unsuspend a suspended Okta user, restoring their sign-in access."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/unsuspend")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User unsuspended."))


@chat.function("deactivate_user", "Deactivate (soft-delete) an Okta user. Okta keeps a 30-day recovery window internally.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.deactivate_user", effects=["okta.user.status_changed"])
async def deactivate_user(ctx, params: UserIdParams) -> ActionResult:
    """Deactivate (soft-delete) an Okta user. Okta keeps a 30-day recovery window internally."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/deactivate")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User deactivated."))


@chat.function("unlock_user", "Unlock a locked-out Okta user.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.unlock_user", effects=["okta.user.unlocked"])
async def unlock_user(ctx, params: UserIdParams) -> ActionResult:
    """Unlock a locked-out Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/unlock")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User unlocked."))


@chat.function("expire_user_password", "Expire an Okta user's password, forcing them to set a new one at next login.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.expire_user_password", effects=["okta.user.password_expired"])
async def expire_user_password(ctx, params: UserIdParams) -> ActionResult:
    """Expire an Okta user's password, forcing them to set a new one at next login."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/expire_password")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Password expired; user must set a new one at next login."))


def _group_entity(g: dict) -> OktaGroup:
    profile = g.get("profile", {}) or {}
    return OktaGroup(
        group_id=g.get("id", ""),
        name=profile.get("name", ""),
        description=profile.get("description", ""),
        group_type=g.get("type", ""),
    )


@chat.function("list_groups", "List Okta groups, optionally filtered by search text.", action_type="read", chain_callable=True, data_model=GroupList, event="okta-connector.list_groups")
async def list_groups(ctx, params: ListGroupsParams) -> ActionResult:
    """List Okta groups, optionally filtered by search text."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 200))}
    if params.q:
        q["q"] = params.q
    try:
        data, _ = await client.request("GET", "/api/v1/groups", params=q)
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=GroupList(groups=[_group_entity(g) for g in (data or [])]))


@chat.function("get_group", "Read one Okta group in full.", action_type="read", chain_callable=True, data_model=OktaGroup, event="okta-connector.get_group")
async def get_group(ctx, params: GroupIdParams) -> ActionResult:
    """Read one Okta group in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/groups/{params.group_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_group_entity(data or {}))


@chat.function("create_group", "Create a new Okta group.", action_type="write", chain_callable=True, data_model=OktaGroup, event="okta-connector.create_group", effects=["okta.group.created"])
async def create_group(ctx, params: CreateGroupParams) -> ActionResult:
    """Create a new Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    body = {"profile": {"name": params.name, "description": params.description}}
    try:
        data, _ = await client.request("POST", "/api/v1/groups", json_body=body)
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_group_entity(data or {}))


@chat.function("list_group_members", "List the members of an Okta group.", action_type="read", chain_callable=True, data_model=UserList, event="okta-connector.list_group_members")
async def list_group_members(ctx, params: GroupIdParams) -> ActionResult:
    """List the members of an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/groups/{params.group_id}/users")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=UserList(users=[_user_entity(u) for u in (data or [])]))


@chat.function("add_user_to_group", "Add a user to an Okta group.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.add_user_to_group", effects=["okta.group.member_added"])
async def add_user_to_group(ctx, params: GroupMemberParams) -> ActionResult:
    """Add a user to an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("PUT", f"/api/v1/groups/{params.group_id}/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User added to group."))


@chat.function("remove_user_from_group", "Remove a user from an Okta group.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.remove_user_from_group", effects=["okta.group.member_removed"])
async def remove_user_from_group(ctx, params: GroupMemberParams) -> ActionResult:
    """Remove a user from an Okta group."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("DELETE", f"/api/v1/groups/{params.group_id}/users/{params.user_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User removed from group."))


def _app_entity(a: dict) -> OktaApp:
    return OktaApp(
        app_id=a.get("id", ""),
        label=a.get("label", ""),
        status=a.get("status", ""),
        sign_on_mode=a.get("signOnMode", ""),
    )


@chat.function("list_apps", "List Okta applications, optionally filtered by search text.", action_type="read", chain_callable=True, data_model=AppList, event="okta-connector.list_apps")
async def list_apps(ctx, params: ListAppsParams) -> ActionResult:
    """List Okta applications, optionally filtered by search text."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    q: dict = {"limit": max(1, min(params.limit, 200))}
    if params.q:
        q["q"] = params.q
    try:
        data, _ = await client.request("GET", "/api/v1/apps", params=q)
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=AppList(apps=[_app_entity(a) for a in (data or [])]))


@chat.function("get_app", "Read one Okta application in full.", action_type="read", chain_callable=True, data_model=OktaApp, event="okta-connector.get_app")
async def get_app(ctx, params: AppIdParams) -> ActionResult:
    """Read one Okta application in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/apps/{params.app_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_app_entity(data or {}))


@chat.function("assign_user_to_app", "Assign an Okta user directly to an application.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.assign_user_to_app", effects=["okta.app.user_assigned"])
async def assign_user_to_app(ctx, params: AssignUserToAppParams) -> ActionResult:
    """Assign an Okta user directly to an application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request(
            "POST", f"/api/v1/apps/{params.app_id}/users",
            json_body={"id": params.user_id, "scope": "USER"},
        )
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="User assigned to application."))


@chat.function("assign_group_to_app", "Assign an Okta group to an application (all group members get access).", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.assign_group_to_app", effects=["okta.app.group_assigned"])
async def assign_group_to_app(ctx, params: AssignGroupToAppParams) -> ActionResult:
    """Assign an Okta group to an application (all group members get access)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("PUT", f"/api/v1/apps/{params.app_id}/groups/{params.group_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Group assigned to application."))


@chat.function("activate_app", "Activate an Okta application.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.activate_app", effects=["okta.app.status_changed"])
async def activate_app(ctx, params: AppIdParams) -> ActionResult:
    """Activate an Okta application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/apps/{params.app_id}/lifecycle/activate")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Application activated."))


@chat.function("deactivate_app", "Deactivate an Okta application.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.deactivate_app", effects=["okta.app.status_changed"])
async def deactivate_app(ctx, params: AppIdParams) -> ActionResult:
    """Deactivate an Okta application."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/apps/{params.app_id}/lifecycle/deactivate")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Application deactivated."))


def _factor_entity(f: dict) -> OktaFactor:
    return OktaFactor(
        factor_id=f.get("id", ""),
        factor_type=f.get("factorType", ""),
        provider=f.get("provider", ""),
        status=f.get("status", ""),
    )


@chat.function("list_user_factors", "List MFA factors enrolled for an Okta user.", action_type="read", chain_callable=True, data_model=FactorList, event="okta-connector.list_user_factors")
async def list_user_factors(ctx, params: ListFactorsParams) -> ActionResult:
    """List MFA factors enrolled for an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}/factors")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=FactorList(factors=[_factor_entity(f) for f in (data or [])]))


@chat.function("reset_user_factors", "Reset ALL enrolled MFA factors for an Okta user -- they must re-enroll at next login. Use when a user has lost their MFA device.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.reset_user_factors", effects=["okta.user.factor_reset"])
async def reset_user_factors(ctx, params: UserIdParams) -> ActionResult:
    """Reset ALL enrolled MFA factors for an Okta user -- they must re-enroll at next login. Use when a user has lost their MFA device."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("POST", f"/api/v1/users/{params.user_id}/lifecycle/reset_factors")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="All MFA factors reset; user must re-enroll at next login."))


def _policy_entity(p: dict) -> OktaPolicy:
    return OktaPolicy(
        policy_id=p.get("id", ""),
        name=p.get("name", ""),
        policy_type=p.get("type", ""),
        status=p.get("status", ""),
    )


@chat.function("list_policies", "List Okta policies of a given type (sign-on, password, MFA enrollment, access).", action_type="read", chain_callable=True, data_model=PolicyList, event="okta-connector.list_policies")
async def list_policies(ctx, params: ListPoliciesParams) -> ActionResult:
    """List Okta policies of a given type (sign-on, password, MFA enrollment, access)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", "/api/v1/policies", params={"type": params.policy_type})
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=PolicyList(policies=[_policy_entity(p) for p in (data or [])]))


@chat.function("get_policy", "Read one Okta policy in full.", action_type="read", chain_callable=True, data_model=OktaPolicy, event="okta-connector.get_policy")
async def get_policy(ctx, params: PolicyIdParams) -> ActionResult:
    """Read one Okta policy in full."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/policies/{params.policy_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_policy_entity(data or {}))


def _role_entity(r: dict) -> AdminRole:
    return AdminRole(
        role_id=r.get("id", ""),
        role_type=r.get("type", ""),
        status=r.get("status", ""),
    )


@chat.function("list_admin_roles", "List admin roles assigned to an Okta user.", action_type="read", chain_callable=True, data_model=RoleList, event="okta-connector.list_admin_roles")
async def list_admin_roles(ctx, params: ListAdminRolesParams) -> ActionResult:
    """List admin roles assigned to an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request("GET", f"/api/v1/users/{params.user_id}/roles")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=RoleList(roles=[_role_entity(r) for r in (data or [])]))


@chat.function("assign_admin_role", "Assign an admin role to an Okta user (e.g. SUPER_ADMIN, ORG_ADMIN, APP_ADMIN).", action_type="write", chain_callable=True, data_model=AdminRole, event="okta-connector.assign_admin_role", effects=["okta.role.assigned"])
async def assign_admin_role(ctx, params: AssignRoleParams) -> ActionResult:
    """Assign an admin role to an Okta user (e.g. SUPER_ADMIN, ORG_ADMIN, APP_ADMIN)."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        data, _ = await client.request(
            "POST", f"/api/v1/users/{params.user_id}/roles",
            json_body={"type": params.role_type},
        )
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=_role_entity(data or {}))


@chat.function("remove_admin_role", "Remove an admin role assignment from an Okta user.", action_type="write", chain_callable=True, data_model=DeleteResult, event="okta-connector.remove_admin_role", effects=["okta.role.removed"])
async def remove_admin_role(ctx, params: RemoveRoleParams) -> ActionResult:
    """Remove an admin role assignment from an Okta user."""
    c = await _resolve_connection(ctx, params.connection_id)
    client = _client_for(c)
    try:
        await client.request("DELETE", f"/api/v1/users/{params.user_id}/roles/{params.role_id}")
    except oc.OktaError as exc:
        return ActionResult.error(str(exc))
    return ActionResult.success(data=DeleteResult(ok=True, detail="Admin role removed."))


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


@chat.function("list_system_log", "List Okta System Log events (audit trail of logins, MFA, admin actions), optionally filtered by time range or SCIM-style filter expression.", action_type="read", chain_callable=True, data_model=SystemLogList, event="okta-connector.list_system_log")
async def list_system_log(ctx, params: ListSystemLogParams) -> ActionResult:
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
        return ActionResult.error(str(exc))
    next_cursor = oc.parse_next_link(headers)
    return ActionResult.success(data=SystemLogList(events=[_log_entity(e) for e in (data or [])], next_cursor=next_cursor))


@chat.function("audit_org", "Build one aggregated health report for the connected Okta org: active/suspended user counts, admin count, and recent failed logins.", action_type="read", chain_callable=True, data_model=HealthAudit, event="okta-connector.audit_org")
async def audit_org(ctx, params: ConnectionRefParams) -> ActionResult:
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
        return ActionResult.error(str(exc))
    return ActionResult.success(data=HealthAudit(
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
