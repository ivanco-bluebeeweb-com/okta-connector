"""Pydantic input contracts and SDL result entities for Okta Connector."""
from __future__ import annotations

from imperal_sdk import sdl
from pydantic import BaseModel, Field


class NoParams(BaseModel):
    pass


class ConnectionRefParams(BaseModel):
    connection_id: str = Field("", description="Optional saved Okta org connection ID. Omit to use the first connected org.")


class ConnectOktaParams(BaseModel):
    label: str = Field("", description="Friendly org label, e.g. 'Acme Production'.")
    org_domain: str = Field(..., description="Okta org domain, e.g. 'acme.okta.com'.")
    auth_mode: str = Field("api_token", description="Authentication mode: 'api_token' or 'oauth2_service_app'.")
    api_token: str = Field("", description="SSWS API Token (required for api_token mode).")
    client_id: str = Field("", description="OAuth2 Service App client ID (required for oauth2_service_app mode).")
    private_key: str = Field("", description="OAuth2 Service App private key PEM (required for oauth2_service_app mode).")


class DisconnectOktaParams(ConnectionRefParams):
    connection_id: str = Field(..., description="Saved Okta org connection ID to remove from Imperal.")


class ListUsersParams(ConnectionRefParams):
    status_filter: str = Field("", description="Optional status filter: ACTIVE, STAGED, SUSPENDED, DEPROVISIONED, etc.")
    q: str = Field("", description="Optional search string matching name/email prefix.")
    limit: int = Field(50, description="Max users to return (1-200).")


class UserIdParams(ConnectionRefParams):
    user_id: str = Field(..., description="Okta user id or login.")


class CreateUserParams(ConnectionRefParams):
    first_name: str = Field(..., description="User's first name.")
    last_name: str = Field(..., description="User's last name.")
    email: str = Field(..., description="User's primary email (also used as login unless login is set).")
    login: str = Field("", description="Login (defaults to email if omitted).")
    activate: bool = Field(True, description="Activate the user immediately (sends activation email unless password set).")


class UpdateUserParams(UserIdParams):
    first_name: str = Field("", description="New first name (optional).")
    last_name: str = Field("", description="New last name (optional).")
    email: str = Field("", description="New email (optional).")


class ListGroupsParams(ConnectionRefParams):
    q: str = Field("", description="Optional search string matching group name prefix.")
    limit: int = Field(50, description="Max groups to return (1-200).")


class GroupIdParams(ConnectionRefParams):
    group_id: str = Field(..., description="Okta group id.")


class CreateGroupParams(ConnectionRefParams):
    name: str = Field(..., description="Group name.")
    description: str = Field("", description="Group description.")


class GroupMemberParams(ConnectionRefParams):
    group_id: str = Field(..., description="Okta group id.")
    user_id: str = Field(..., description="Okta user id.")


class ListAppsParams(ConnectionRefParams):
    q: str = Field("", description="Optional search string matching app label prefix.")
    limit: int = Field(50, description="Max apps to return (1-200).")


class AppIdParams(ConnectionRefParams):
    app_id: str = Field(..., description="Okta application id.")


class AssignUserToAppParams(ConnectionRefParams):
    app_id: str = Field(..., description="Okta application id.")
    user_id: str = Field(..., description="Okta user id.")


class AssignGroupToAppParams(ConnectionRefParams):
    app_id: str = Field(..., description="Okta application id.")
    group_id: str = Field(..., description="Okta group id.")


class ListFactorsParams(UserIdParams):
    pass


class ListPoliciesParams(ConnectionRefParams):
    policy_type: str = Field("OKTA_SIGN_ON", description="Policy type: OKTA_SIGN_ON, PASSWORD, MFA_ENROLL, ACCESS_POLICY.")


class PolicyIdParams(ConnectionRefParams):
    policy_id: str = Field(..., description="Okta policy id.")


class ListSystemLogParams(ConnectionRefParams):
    since: str = Field("", description="ISO 8601 start time, e.g. '2026-08-01T00:00:00Z'.")
    until: str = Field("", description="ISO 8601 end time.")
    filter_expr: str = Field("", description="Okta System Log SCIM-style filter expression, e.g. \"eventType eq \\\"user.session.start\\\"\".")
    q: str = Field("", description="Free-text search across log events.")
    limit: int = Field(100, description="Max events to return (1-1000).")


class ListAdminRolesParams(UserIdParams):
    pass


class AssignRoleParams(UserIdParams):
    role_type: str = Field(..., description="Okta admin role type, e.g. 'SUPER_ADMIN', 'ORG_ADMIN', 'APP_ADMIN'.")


class RemoveRoleParams(ConnectionRefParams):
    user_id: str = Field(..., description="Okta user id.")
    role_id: str = Field(..., description="Okta role assignment id.")


# ---- SDL entities ----

class OktaConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connection_id: str
    label: str
    org_domain: str
    auth_mode: str


class ConnectionList(sdl.Entity):
    id: str = ""
    title: str = ""
    connections: list[OktaConnection]


class OktaUser(sdl.Entity):
    id: str = ""
    title: str = ""
    user_id: str
    login: str
    email: str
    first_name: str
    last_name: str
    status: str
    created: str


class UserList(sdl.Entity):
    id: str = ""
    title: str = ""
    users: list[OktaUser]


class OktaGroup(sdl.Entity):
    id: str = ""
    title: str = ""
    group_id: str
    name: str
    description: str
    group_type: str


class GroupList(sdl.Entity):
    id: str = ""
    title: str = ""
    groups: list[OktaGroup]


class OktaApp(sdl.Entity):
    id: str = ""
    title: str = ""
    app_id: str
    label: str
    status: str
    sign_on_mode: str


class AppList(sdl.Entity):
    id: str = ""
    title: str = ""
    apps: list[OktaApp]


class OktaFactor(sdl.Entity):
    id: str = ""
    title: str = ""
    factor_id: str
    factor_type: str
    provider: str
    status: str


class FactorList(sdl.Entity):
    id: str = ""
    title: str = ""
    factors: list[OktaFactor]


class OktaPolicy(sdl.Entity):
    id: str = ""
    title: str = ""
    policy_id: str
    name: str
    policy_type: str
    status: str


class PolicyList(sdl.Entity):
    id: str = ""
    title: str = ""
    policies: list[OktaPolicy]


class SystemLogEvent(sdl.Entity):
    id: str = ""
    title: str = ""
    uuid: str
    published: str
    event_type: str
    actor: str
    outcome_result: str
    outcome_reason: str


class SystemLogList(sdl.Entity):
    id: str = ""
    title: str = ""
    events: list[SystemLogEvent]
    next_cursor: str


class AdminRole(sdl.Entity):
    id: str = ""
    title: str = ""
    role_id: str
    role_type: str
    status: str


class RoleList(sdl.Entity):
    id: str = ""
    title: str = ""
    roles: list[AdminRole]


class HealthAudit(sdl.Entity):
    id: str = ""
    title: str = ""
    org_domain: str
    active_users: int
    suspended_users: int
    admin_count: int
    failed_logins_24h: int
    notes: str


class DeleteResult(sdl.Entity):
    id: str = ""
    title: str = ""
    ok: bool
    detail: str
