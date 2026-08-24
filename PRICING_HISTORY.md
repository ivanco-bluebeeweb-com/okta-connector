# Pricing History — Okta Connector

## 2026-08-24 — initial pricing (build → deploy → update_pricing → submit_for_review)

Same pattern as MuleSoft/Asana/HubSpot/Klaviyo/Webflow/Salesforce this same
build cycle: pricing set via `developer.update_pricing` (canonical call, NOT
`save_pricing`) BEFORE `submit_for_review`, per the standing rule ("ты не
выставила прайсинги на функции перед заливом на платформу... это должно быть
частью дефолтного поведения всегда для всех приложений и для всех сессий").

**First call failed with the same silent-mismatch pattern documented for
MuleSoft** — response reported `model stored as 'free'` and every
`tool_prices` key "not stored" despite no error being raised by the API.
Immediate retry with the identical payload succeeded. Same conclusion as the
MuleSoft precedent: worth a platform bug ticket (see below), not a client-side
mistake — retry once with the identical payload before assuming failure.

**Prices — fixed platform scale {0, 8, 16, 20, 40, 60}, no exceptions, no
markup (Okta is not a Google-backed metered API):**

| Цена | Функции |
|---|---|
| 0 | `connect_okta`, `disconnect_okta`, `list_connections` (настройка доступа, не операция с Okta API) |
| 8 | `list_users`, `get_user`, `list_groups`, `get_group`, `list_apps`, `get_app`, `list_user_factors`, `list_policies`, `get_policy`, `list_admin_roles`, `list_system_log`, `list_group_members` (простое чтение состояния) |
| 16 | `create_user`, `update_user`, `activate_user`, `suspend_user`, `unsuspend_user`, `deactivate_user`, `unlock_user`, `create_group`, `add_user_to_group`, `remove_user_from_group`, `assign_user_to_app`, `assign_group_to_app`, `activate_app`, `deactivate_app`, `assign_admin_role`, `remove_admin_role` (стандартное одиночное write/destructive-действие) |
| 20 | `expire_user_password`, `reset_user_factors` (security-критичное действие, влияющее на доступ пользователя немедленно) |
| 40 | `audit_org` (агрегированный value-add отчёт по всей org: active/suspended users, admin count, failed logins) |

`pricing_model = "per_action"`, `monthly_price = 0`, `revenue_split_dev = 95`
(partner tier).

**Обязательный журнал**: каждое выставление или изменение цен на функции
этого приложения фиксируется здесь — что изменилось, почему, и на основании
чего. Не переписывать прошлые записи — только дописывать новые сверху.
