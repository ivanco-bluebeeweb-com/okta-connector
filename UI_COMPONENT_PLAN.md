# Okta Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `okta-connector`.

## 0. Разница с IDEAL_ONBOARDING.md
Идеал предполагает интерактивный чеклист OAuth-scopes и мгновенную проверку через реальный
вызов API прямо в форме подключения. Реализация делает проверку тем же способом, что и
другие OAuth/Token коннекторы портфеля (ServiceNow, SAP) — `connect_okta` сам выполняет
пробный запрос перед сохранением, форма показывает результат через стандартный
error/success путь `ui.Form`. Scope-чеклист описан текстом (`ui.Text` + `ui.Markdown`),
не интерактивными переключателями (SDK не имеет per-scope toggle привязанного к одной форме).

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left, not connected) | `ui.Stack`(v, align="stretch") + `ui.Text`(subtitle) + `ui.Form`(connect_okta) с лейблами на каждом `ui.Input`/`ui.Select` + `ui.Button`("How do I get this?" → help dialog) | Без карточек, без дублирования инструкций — паттерн Webflow/MuleSoft/ServiceNow. Форма растянута на всю ширину сайдбара. |
| Connect form fields | `ui.Select`(auth mode: api_token/oauth2_service_app) + labelled `ui.Input`(org domain, placeholder "acme.okta.com") + условные поля (API token ИЛИ client_id/private_key) | Select переключает набор полей — оба режима реально поддерживаются. |
| Help dialog | `ui.Dialog` (или `ui.panel(center_overlay=True)`) + `ui.Markdown`(шаги для API Token и для OAuth2 Service App, включая список нужных scopes) | Единственное место с инструкциями подключения — не дублируется в сайдбаре. |
| Sidebar (connected) | `ui.Stack`(v) + `ui.Text`(org domain label) + `ui.Divider` + `ui.Button`×5 (Users/Groups/Applications/Policies/System Log) + `ui.Button`("App settings") | Плоский список разделов, без карточек, "App settings" всегда последним. |
| Users list (center, `center_overlay=True`) | `ui.Header` + `ui.Select`(status filter: active/suspended/deactivated) + `ui.DataTable`(login/email/status/created) + row action `ui.Button`("Open") | Табличный список — стандартный паттерн для списков записей. |
| User detail | `ui.Stack`(v) + `ui.KeyValue`(profile fields) + `ui.List`(enrolled MFA factors) + `ui.Button`("Suspend"/"Activate", confirm=true) + `ui.Button`("Reset MFA factors", variant="destructive", confirm=true) | KeyValue для профиля, деструктивные действия — с native confirm. |
| Groups list | `ui.DataTable`(name/type/member count) + row → detail with `ui.List`(members) + `ui.Button`("Add member") | Тот же табличный паттерн. |
| Applications list | `ui.DataTable`(label/status/sign_on_mode) + row → assigned users/groups `ui.List` | Единообразно со списком групп. |
| System Log viewer | `ui.Header` + `ui.Select`(event type filter) + date range inputs + `ui.DataTable`(time/actor/event_type/outcome) with cursor "Load more" `ui.Button` | Log — типично табличный с курсорной пагинацией, не offset-based. |
| Org health (audit_org value-add) | `ui.Stats`(suspended count / admin count / failed logins 24h) + `ui.Alert`(warn) if spike detected | Stats-панель для быстрого обзора, как в других коннекторах (MuleSoft/GitLab audit). |
| App settings (center, `center_overlay=True`, separate panel) | `ui.Header` + per-connection `ui.Stack`(h) row: label + `ui.Button`("Disconnect", variant="destructive") | Disconnect живёт только тут, не дублируется в сайдбаре. |

## 2. Формы: лейблы, плейсхолдеры, растяжение
Все инпуты — с явными `ui.Text`(variant="label") лейблами через хелпер `_field()`.
Плейсхолдеры контекстные: "acme.okta.com" для домена, "00abc...xyz" для API token.
Контейнер `ui.Form` в сайдбаре растянут на всю ширину (`align="stretch"` на родительском
Stack), содержимое формы растянуто внутри себя тем же `align="stretch"`.

## 3. Пустое состояние центра
Базовая (non-overlay) center-панель с каноничным текстом "Nothing to show here" до выбора
раздела в сайдбаре — регистрируется отдельно, всегда есть даже когда все overlay-панели
закрыты.
