# Okta Connector — Preparation

**Version:** 0.1.0 (planning)
**Date:** 2026-08-24
**Related task:** BBW Imperal Apps #2452
**Scope decision:** maximum feasible capability against the publicly documented Okta
Management API + System Log API (per standing "максимальный функционал" instruction).

## 1. App passport

**Name:** Okta Connector
**One-line purpose:** Connect your own Okta org (API Token or OAuth2 Service App) to
manage Users, Groups, Applications, MFA Factors, Policies, admin Roles and Sessions,
plus stream the System Log for security/audit visibility.

**What it is not:**
- Not Okta Workflows (no-code automation builder) — separate product surface.
- Not API Access Management (custom Authorization Servers / OAuth scope design) —
  Tier 2/future, a distinct advanced product SKU.
- Not Okta Identity Governance (access certifications/reviews) — separate SKU.

## 2. Human problem

> An IT admin or security engineer running Okta needs to provision/deprovision users,
> triage suspicious sign-ins, reset a locked-out user's MFA, or get a live view of who
> has admin rights — without opening the Okta Admin Console for every routine task.

### Personas
| Persona | Trigger | Value |
|---|---|---|
| IT admin | New hire needs an account + app access | create_user + assign to group/app in one flow |
| Security engineer | Investigating a suspicious login | list_system_logs filtered by user/event type |
| Helpdesk agent | User locked out / lost MFA device | reset_user_factors, unlock_user |
| Okta org admin | Wants an org health snapshot | audit_org — suspended users, admins, recent failed logins |
| Compliance officer | Needs to see who holds admin roles | list_admin_role_assignments across users/groups |

## 3. Scope tiers

**Tier 1 (this release):**
- connect_okta (API Token or OAuth2 Service App client-credentials-with-JWT), disconnect_okta, list_connections
- Users: list, get, create, update, activate, suspend, unsuspend, deactivate, unlock, expire_password
- Groups: list, get, create, list_members, add_user_to_group, remove_user_from_group
- Applications: list, get, list_app_users, assign_user_to_app, assign_group_to_app, deactivate_app_user_assignment
- Factors (MFA): list_user_factors, reset_user_factors (remove all — recovery flow)
- Policies: list_policies (by type: OKTA_SIGN_ON, PASSWORD, MFA_ENROLL), get_policy
- Roles: list_user_roles, assign_user_role, remove_user_role, list_admin_role_assignments (value-add across org)
- Sessions: list_user_sessions (via factors/sessions), clear_user_sessions (force logout)
- System Log: list_system_log_events (cursor pagination via Link header, filters: since/until/filter/q)
- Value-add: audit_org (suspended users count, active admins count, recent failed-login spike from System Log)

**Tier 2 (future):** custom Authorization Servers, OAuth scope management, Okta
Workflows triggers, Identity Governance access reviews, Inline Hooks management.

## 4. Auth model detail

Two connect modes (mirrors ServiceNow's basic/oauth2 select pattern):
1. **API Token (`sswsToken`)** — `Authorization: SSWS {token}` header. Simplest; token
   inherits the permissions of the admin who created it in Okta Admin Console
   (Security > API > Tokens). No expiry unless the creating admin's session invalidates it
   or it's manually revoked.
2. **OAuth2 Service App (client credentials + private key JWT)** — Okta's recommended
   production-grade method: register a Service App in Admin Console, generate a key pair,
   Imperal signs a client_assertion JWT and exchanges it at `/oauth2/v1/token` for a scoped
   access token (short-lived, auto-refreshed). Requires explicit OAuth scopes granted
   per capability (e.g. `okta.users.manage`, `okta.groups.manage`).

Both modes save only the Okta org domain + token/keypair reference — never the resulting
bearer token itself long-term (OAuth2 tokens are cached in-memory with expiry, matching
the ServiceNow OAuth2 pattern).

## 5. Safety notes (see APP_SAFETY_CHECKLIST.md)

- `reset_user_factors` and `clear_user_sessions` are destructive-adjacent (force a user
  to re-enroll MFA / re-authenticate everywhere) — require explicit confirmation copy.
- `deactivate_user` is Okta's soft-delete equivalent (30-day undo window in Okta itself);
  worth noting in the tool description so agents don't treat it as instantly permanent.
- System Log events may contain PII (IP addresses, user agent strings) — pass through
  as-is (Okta's own data), no extra redaction beyond what Okta returns.
