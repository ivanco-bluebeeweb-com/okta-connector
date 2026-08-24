# Okta Connector — Connector Discovery

**Discovery date:** 2026-08-24
**Release scope:** maximum functionality against the publicly documented Okta
Management API (per standing "максимальный функционал" instruction).
**Related task:** BBW Imperal Apps #2452.

## 1. What Okta actually is

Okta is a cloud identity provider (IdP): SSO, MFA, lifecycle management (provisioning/
deprovisioning), and API Access Management, all exposed through one REST surface, the
**Okta Management API** (`https://{yourOktaDomain}/api/v1/*`), plus a separate
**System Log API** for audit/security event streaming.

## 2. Chosen integration surface

**Okta Management API v1** (`/api/v1/*`):
- Users (`/users`) — full lifecycle: create, activate, suspend, unsuspend, deactivate,
  reset password, reset MFA factors, unlock.
- Groups (`/groups`) — create, list, add/remove members, assign apps.
- Applications (`/apps`) — list, get, assign users/groups, activate/deactivate.
- Factors (`/users/{id}/factors`) — list enrolled MFA factors, enroll, verify, reset.
- Policies (`/policies`) — sign-on, password, MFA enrollment policies (read + list;
  full policy authoring is complex rule-tree editing, exposed as typed create/update
  for the common policy types).
- Roles (`/users/{id}/roles`, `/groups/{id}/roles`) — admin role assignment.
- Sessions (`/sessions`) — admin-initiated session lookup/clear (force logout).
- **System Log API** (`/api/v1/logs`) — audit trail: logins, MFA events, admin actions,
  cursor-paginated via `Link` response headers (not offset/limit).

Not in scope for v1 (Tier 2/future): custom Authorization Servers / OAuth scope
management (API Access Management — a separate, more advanced product surface),
Okta Workflows, Identity Governance (Okta Identity Governance is a separate SKU).

## 3. Auth model

Two connect modes, both explicitly supported by Okta:
1. **SSWS API Token** — simplest: an admin generates a token in Okta Admin Console
   (Security > API > Tokens), inherits that admin's permissions. Passed as
   `Authorization: SSWS {token}`. No expiry unless the issuing admin's session/account
   changes; Okta does auto-expire tokens unused for 30 days.
2. **OAuth 2.0 Client Credentials** (recommended by Okta for production/service
   integrations) — a Service App (API Services app type) registered in Okta Admin
   Console with a private key (JWT client assertion), token endpoint
   `/oauth2/v1/token`. More setup but more auditable and scoped.

Both require the **Okta domain** (`{yourOktaDomain}.okta.com` or a custom domain) as a
first-class field, same pattern as ServiceNow's instance_host.

## 4. Terminology / API notes

- Every resource has a stable `id` (not `sys_id`-style) — standard REST id semantics,
  simpler than ServiceNow's GUID convention.
- Filtering uses SCIM-flavored `filter=` query params on some endpoints (e.g.
  `/users?filter=status eq "ACTIVE"`) and simple `search=`/`q=` on others — the client
  exposes both as passthrough params per typed function, matching what the specific
  endpoint actually accepts (don't invent a universal filter DSL).
- Pagination: cursor-based via RFC 5988 `Link` headers (`rel="next"`) — NOT
  offset/limit. The client follows `Link` headers internally up to the requested limit.
- Rate limits: org-wide + per-endpoint, surfaced via `X-Rate-Limit-Limit` /
  `X-Rate-Limit-Remaining` / `X-Rate-Limit-Reset` response headers — client raises a
  retryable error with the reset time when a 429 is hit.
- User lifecycle states are explicit and modeled (STAGED, PROVISIONED, ACTIVE,
  RECOVERY, PASSWORD_EXPIRED, LOCKED_OUT, SUSPENDED, DEPROVISIONED) — surfaced as-is,
  not remapped to a generic "active/inactive" boolean, since the distinction matters
  operationally (e.g. LOCKED_OUT vs SUSPENDED need different remediation).

## 5. Scope decision (Tier 1 = v1)

**Tier 1 (this release):**
- connect_okta (API Token or OAuth2 client-credentials mode) / disconnect_okta /
  list_connections.
- Users: list_users, get_user, create_user, update_user, activate_user,
  suspend_user, unsuspend_user, deactivate_user, unlock_user, expire_password,
  reset_password (sends recovery link), reset_factors.
- Groups: list_groups, get_group, create_group, add_user_to_group,
  remove_user_from_group, list_group_members.
- Applications: list_apps, get_app, assign_user_to_app, assign_group_to_app,
  list_app_assignments.
- Factors (MFA): list_user_factors, enroll_factor, activate_factor, reset_user_factor.
- Policies: list_policies (by type: sign-on, password, MFA enroll), get_policy.
- Roles: list_user_roles, assign_role_to_user, remove_role_from_user.
- Sessions: list_user_sessions (via factors/sessions endpoints), clear_user_sessions
  (force logout everywhere).
- System Log: list_system_logs (audit/security events, filtered by date/event type).
- Value-add: audit_org_health (locked-out users, suspended users, users pending
  activation > N days, admin role count, recent failed-login spike from System Log).
- Bulk: bulk_suspend_users, bulk_deactivate_users (explicit id lists).

**Tier 2 (future):** custom Authorization Servers / scopes, Okta Workflows,
Identity Governance, Inline Hooks management, Brand/theme customization.

## 6. Security notes

- API Token / OAuth2 client credentials (private key) stored as one encrypted JSON
  blob per connection, matching ServiceNow/SAP/Oracle pattern.
- Deactivate/suspend/clear_sessions are destructive-adjacent (immediately affect a
  real employee's access) — flagged clearly in tool descriptions, no silent defaults.
- reset_password/reset_factors never return the new credential itself — Okta's own
  flow emails/sends the recovery link or push challenge; this connector never handles
  a raw password or OTP secret.
