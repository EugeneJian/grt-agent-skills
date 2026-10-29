# Ecology API schema (service-derived)

Field-level reference for company-domain contract **1.34.0**, synchronized on 2026-10-29 from the service owner's generated OpenAPI and verified HTTP/MCP behavior. The connected service remains authoritative. Source OpenAPI SHA-256: `fa824776aa81d217b337a8d15be594af76ddc1398af46656bca04d362642709a`. This is a reference projection, not an independent rule source. All nine operations use the same schemas over HTTP and cloud MCP.

Use `https://ecology.growatt.com/api/v1/ecology` with credentials authorized for that route. Preserve an explicitly configured alternative deployment and check its advertised inputs; a matching paging shape alone does not prove support for 1.34 single-inverter selection. This document describes the current company-domain contract, not legacy request forms.

## Common conventions

- Base `https://ecology.growatt.com/api/v1/ecology`; auth `Authorization: Bearer <Key or employee OAuth token>`. Never place credentials in URLs or output.
- Exact market codes: `AE AT AU BE BG BR CA CH CL CN CO CY CZ DE DK EE ES FI FR GB GE GR HR HU IE IL IN IQ IS IT JO JP KR LT LU LV MT MX NA NG NL NO NZ PH PK PL PT RO SA SE SI SK TH TW US VN ZA`, plus regional `EUROPE` and `GENERIC`. `GLOBAL` is not a valid API market; discover all granted markets with `portfolio` by omitting `market` or using `all`, then use an exact returned market for product/model queries.
- Version pins are 64-char hex. `version` of a single-product read is that product's version in that market and `sku_version` (from `models`/`materials`) is that product's SKU slice; take both from reads of the same product and market, never from discovery or another product. Discovery accepts no pins, `models` no `sku_version`; `meta.catalog_version` is diagnostic only.
- Pagination: omit `page_token` for the first page, then send `meta.next_page_token` unchanged with the same filters and pins until it is `null`; `limit` defaults to 50 (maximum 500) and may change between pages. A changed filter returns 400 at `/page_token`; a changed list returns 409 `list_changed` (restart from the first page). `offset` is read-only response metadata and is rejected as an input. Pages are bounded to 2 MiB (`meta.page_limited_by_bytes` marks a byte-truncated page). A single oversized row returns 413 `response_too_large`.
- Envelope: `{ "data": …, "meta": …, "request_id": <uuid> }`. Common `meta`: `generated_at`, `expires_at`, `language` (`en`/`zh-CN`), `version`, `rules_version {data, engine, runtime}`, `market_context? {kind, market, message, automatic_market_merge: false, approval: "not_assessed"}`, and for paged reads `total`, `offset`, `limit`, `requested_limit?` and `next_page_token` (`null` on the last page); every response adds `catalog_version`. Model-returning reads add `sku {version, expires_at}` and `models_status` (`ok`/`empty`). Aggregate products adds `authorized_markets[]` (the credential's grants, stated once rather than per card). Portfolio, products and product add `lifecycle_source` (`sku_projection`: card EOL read from the published card mapping that Web uses; `unavailable`: mapping unreadable, EOL unknown).
- Errors: `{error: {code, message, next_action, retryable, issues?, recovery?, reason?}, request_id}`. Branch on `code`, then on optional `reason`; never parse prose.
  - 400/422: fix the fields named in `issues[].path` (for example `/scheme_id`, `/component_ids/1`, `/balcony`); values are never echoed. Do not retry unchanged.
  - 401: credential missing, expired or revoked. 403 `forbidden`: `reason` `scope_missing` or `market_not_granted` needs an administrator grant (portfolio `endpoints[].required_scopes` shows current scopes); `origin_not_allowed` means call server-side.
  - 404 `not_found`: without a reason the product is unknown or not visible to this credential. Reasons: `market_country_mismatch` and `model_not_in_market` (copy exact values from `models`); `market_not_available` (authorized but unpublished; choose a market returned by portfolio); `unknown_endpoint` (wrong path).
  - 409 `version_changed`/`sku_version_changed`: read `error.recovery.stale`, refresh the indicated resources and review changed facts; do not merely replace pins. They occur only when data the product depends on changed. 409 `list_changed`: restart that list. 413: request less detail. 429: stop the batch and honor `Retry-After`.
  - 503: retry only when `retryable` is true (`service_temporarily_unavailable`, `database_temporarily_unavailable`, `request_timeout`), after `Retry-After`, within a bounded budget. Otherwise report the code and `request_id`.

## Single-inverter selection

For a country and rated power, call `GET /market-models?market=AU&selection_mode=inverter_only&power_kw=5` or `ecology_market_models({"market":"AU","selection_mode":"inverter_only","power_kw":5})`. When a product ID is known, use its `/models` route or `ecology_models` with the same fields. Both need only `catalog:read` and do not query PNs.

Each returned row's `selection: {kind: "inverter_only", quantity: 1}` is an independent alternative, never an additive BOM line. Use the returned rating exactly; do not round, substitute the nearest rating or infer a missing rating from its name. These requests do not take battery capacity, phase, a system scheme or rule pins and do not call `evaluate`. Pending system rules cannot block an independently supported single-inverter candidate.

`unit_selection` on a card is capability, while `selectable_markets` and model responses describe current availability. Non-EOL on-grid PV, battery-ready, hybrid, off-grid and AC-coupled inverter categories are eligible; EOL, batteries, accessories and complete all-in-one systems are excluded from this mode. A data gap remains empty or unavailable, not fabricated compatibility. Successful empty results are not a retry signal; `no_matching_models` may mean the exact kW filter has no match, while `no_models_in_market` means no records in scope. Missing required kW returns 400 `invalid_request` with issue `inverter_power_required` at `/power_kw`.

Keep `market`, `search`, `selection_mode` and `power_kw` unchanged while paging. A changed power or mode invalidates that page token. Normal model inspection without this mode remains available and does not attach a one-unit selection result. HTTP/MCP do not save personal Web selections or approve operation, compatibility, certification or orders.

## GET /portfolio (`ecology_portfolio`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum \| `all` \| string \| null | Omitted/null/blank/`all` = all authorized markets. |

Response `data`: `endpoint_access_meaning` (scope only); `endpoints[] {available, method, operation, path, required_inputs[], required_scopes[], tool}`; `market`; `authorized_markets[] {code, name}` (authorization scope); `product_count`. It contains no product cards and accepts no version pin. No pagination.

## GET /products (`ecology_products`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum | Exact market required. |
| `search` | string ≤100 | Optional text search. |
| `capability` | enum | `New` \| `VPP` \| `Smart scheduling` \| `ShinePhone2.0` \| `Grominder` (Chinese values retained as legacy aliases). |
| `page_token` / `limit` | string / int | See pagination. |

Response `data[]`: summary cards `{id, name, categories[], capabilities[], lifecycle {is_eol, is_new}, selectable_markets, documentation_status, calculation_status, unit_selection?}`. `selectable_markets` is the granted material-backed selection scope (`null` means unknown). Optional `unit_selection: {kind: "inverter_only", quantity: 1}` declares the standalone entry independently of system calculation; it does not prove current candidates. Read details, `url`, `image_url`, `rule_coverage` and `next_actions` from the product resource.

## GET /market-models (`ecology_market_models`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum | **Required**, exact market. |
| `search` | string ≤100 | Matches products/aliases/nameplates. |
| `page_token` / `limit` | string / int | No pins (`meta.sku.version` is the market-wide view, diagnostic only). |
| `selection_mode` | `"inverter_only"` | Optional; requires `power_kw`. |
| `power_kw` | number > 0 | Exact rated kW; required with `inverter_only`, otherwise optional. HTTP query numbers are parsed; MCP uses numeric JSON. |

Response `data[]`: `product_id`, `product_name`, `nameplate`, `power_kw` (number \| null), `countries[]` (exact labels), `association_basis` (`series_country` \| `nameplate_country`; provenance, not qualification), `country_options[]? {country, country_label?, market_code?}`, optional `selection {kind: "inverter_only", quantity: 1}`. `meta` adds `sku`, `models_status`, `models_message` and, for an empty result, `models_empty_reason` (`no_matching_models`: no rows match the search, exact power or selection mode; keep the requested scope unless the user changes it; `no_models_in_market`: no records in this scope).

## GET /products/{product} (`ecology_product`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path, `[A-Za-z0-9_-]{1,80}` | From discovery; never invent ids. |
| `market` | enum | **Required**, exact market. |
| `version` | 64-hex | Optional pin. |

Response `data`: card detail fields including optional `unit_selection`, plus `next_actions[] {operation, tool, method, path, required_scopes[], required_inputs[], depth, status: available|scope_missing|not_selectable_in_market|not_implemented|unavailable|unknown}`, plus `rule_coverage.calculation.bounds? {battery_min, battery_max, module_kwh, cluster_count? (1–3), max_clusters?, phase, powers_kw[], scheme_id?}` and `schemes?[]` of the same shape.

## GET /products/{product}/description (`ecology_description`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path | — |
| `market` | enum | Exact market. |
| `locale` | `en` \| `zh-CN` | — |
| `version` | 64-hex | Optional pin. |

Response `data`: `name`, `product`, `market`, `status: available|not_recorded`, `scope: "product_reference_not_market_approval"`, `introduction`, `sections[]`, `features[]`, `content.modules[]` (`introduction`, `online-resources` items `{label,url}`, `rules` with `variants[]`), `maintenance {rule_version, updated_at}`, `source_url`, `sources[]`.

## GET /products/{product}/rules (`ecology_rules`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path | — |
| `market` | enum | Exact market. |
| `version` | 64-hex | Optional pin. |

Response `data` (key fields): `product`, `market`, `status`, `orderable: false`, `compatibility: "unknown"`, `battery_model`, `limitations[]`, `source_url`, `coverage` (same shape as product `rule_coverage`), `components[] {id, name, component_id?, selectable, supply_class: included|required_separate|optional|unknown, quantity_per_system, quantity_per_inverter, unit, scheme_scope[], selection_group: meter|collector|null, choice_group, open_questions[], rule_version, review_state, scope_status}`, and for adapted products `rule_block`: `{id, version, schema_version: 1, status: "partial", admission?, capabilities {storage}, scope {family, market, scheme_id, inverter_count, assembly?}, inputs {phase: single|three, powers_kw[], battery_min?, battery_max?, module_kwh?, cluster_count?}, meter_requirement: required|not_required|unknown|customer_choice_if_absent, meter_policy?, components[] {id, role, name, supply, quantity {kind: calculated|selected|per_inverter|per_cluster|per_module, value?}, material selector: power|nameplate|meter|binding|unmapped}, steps[] {id, kind, when}, unresolved[]}`; optional `schemes[]`, `balcony {model, channel: "offline", scenarios[] {id, label, fields[] {key, minimum, default, rule_id}}, inputs[], accessories[]?, rules[], admission?, limitations[], reviewed_at, rule_version, source_label, source_revision}`, `battery_reference?`, `workflow? {scheme_id, included[] {role: collector|ct|communication_cable|battery_base, quantity, supply: "included"}, meter_requirement}`.

## GET /products/{product}/models (`ecology_models`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path | — |
| `market` | enum | **Required**, exact market. |
| `page_token` / `limit` | string / int | See common pagination. |
| `version` | 64-hex | Optional product pin. |
| `selection_mode` | `"inverter_only"` | Optional; requires `power_kw`. |
| `power_kw` | number > 0 | Exact rated kW; required with `inverter_only`, otherwise optional. HTTP query numbers are parsed; MCP uses numeric JSON. |

Response `data[]`: `nameplate`, `power_kw`, `countries[]`, `association_basis`, `country_options[]?`, optional `selection {kind: "inverter_only", quantity: 1}`. `meta` adds `sku {version, expires_at}`, `models_status` (`ok`/`empty`), `models_message` and `models_empty_reason?`; an empty list is a successful result.

## GET /products/{product}/materials (`ecology_materials`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path | — |
| `market` | enum | Exact market. |
| `nameplate` | string 1–160 | Exact nameplate from `models`. |
| `country` | string 1–80 | Exact country label from `models`. |
| `coo` | `CN` \| `VN` \| `all` | Required to use any preference/details flag. Default preference: `CN`. |
| `include_details` | bool | Returns `specification`, `description`, derived `coo`. Requires `coo`. |
| `hide_z4` | bool | Default false (Active/blank + Z4 retained); Z1 always excluded. Requires `coo`. |
| `exclude_ecommerce` | bool | Default true when `coo` is set. Requires `coo`. |
| `version`, `sku_version` | 64-hex | Optional pins from this product's `models`/`materials` in this market. |
| `page_token` / `limit` | string / int | See common pagination. |

Response `data[]`: `pn`, `nameplate`, `country`, `country_label?`, `market_code?`, `status: Active|Z4`, `coo?` (CN|VN|null, with details), `specification?`, `description?`. An empty complete result adds `meta.materials_empty_reason` (`filtered_out`: review origin/status preferences; `no_candidates`: none for this exact model and country) and `materials_message`; never substitute another country.

## POST /configurations/evaluate (`ecology_evaluate`)

Request body (JSON):

| Field | Type | Notes |
| --- | --- | --- |
| `product`, `market` | string / enum | Exact market. |
| `scheme_id` | string | When the product exposes schemes. |
| `phase` | `single` \| `three` | Standard families; from rule bounds. |
| `power_kw`, `capacity_kwh` | number > 0 | Standard families send `phase`, `power_kw` and `capacity_kwh` together (missing any one returns 400), even with `scheme_id`. Use values from rule bounds/schemes (`powers_kw`, `module_kwh` multiples). Misaligned sizing returns `no_match` / `outside_coverage`. |
| `has_meter` | bool | MINA: omit when meter ownership is unknown. |
| `component_ids` | string[] ≤50 | Optional selectable components from `rule_block` (`^[a-z][a-z0-9-]{0,79}$`). Do not combine with `accessory_ids`. |
| `accessory_ids` | string[] ≤50 | Legacy opaque IDs `rule-` + 24 hex from `rules.components` for component-quantity families; MINA meter selection requires `has_meter: false`. |
| `balcony` | object | NOAH/NEXA/AURA: `{channel: "offline", scenario?, values {key: integer 0–10000}, accessories?[]}` from rules; replaces phase/power/capacity, not the pins. `values` is required: only the selected scenario's field keys (others return 422 `configuration_input_invalid`), `{}` when the scenario has no fields. |
| `resolve_materials` | bool | Explicit PN work only; `true` requires `materials:read`, `coo` and `sku_version`. |
| `coo` | `CN` \| `VN` \| `all` | Required when `resolve_materials: true`. |
| `hide_z4` | bool | With `resolve_materials`; default false (Active/blank and Z4 retained); Z1 always excluded. |
| `exclude_ecommerce` | bool | With `resolve_materials`; default true. |
| `version` | 64-hex | **Required** for every evaluation, balcony included: from the `product` or `rules` read of the same product and market. |
| `rules_version` | object | **Required** together with `version`: the full `meta.rules_version` object `{data, engine, runtime}` copied from the same read. A bare hash string is rejected. |
| `sku_version` | 64-hex | Required when `resolve_materials: true`; from `models` or `materials` of the same product and market. |
| `component_selections` | array | Stateless revalidation: `{component_id, pn, nameplate, country}` copied from chosen candidates. |

Response `data`: `status: technical_reference|pending_rules|coming_soon|no_match`; `evaluation {calculation: executed_partial|not_implemented|not_evaluated|outside_coverage, compatibility: "unknown", orderable: false}`; legacy `configurations[] {capacity_kwh?, items[] {role, quantity|null, unit, material?}}`; `proposal?` `{schema_version: 1, status: "draft", market, product, rule {id, version}, inputs, lines[] {id, component_id, role, name, quantity|null, unit, supply: separate|included|optional|external, review_status: "pending_review", rule_version, material {candidates[] {pn, nameplate?, country?, country_label?, market_code?, specification?, description?, status?, selection?}, source: D1_material_backup|Feishu_accessory_binding|null, status, binding?}}, meter? {requirement, status}, performance?, topology? {nodes[], edges[]}, unresolved[]}`; `selected_accessories[]?`; `selection_verification? {checked_at, scope: "current_component_candidates_only", checks[] {component_id, selection {pn, nameplate, country}|null, status: confirmed|pending|needs_review|unverified}}`; `rule_admission?`; `checks?[]`; `summary? {materials_requested?, calculation, configuration_count, component_count, quantity_pending_count, material_gap_count, unselected_count, unverified_selection_count, confirmed_selection_count, failed_check_count, unchecked_count, unresolved_count, next_actions[] (review_rules|resolve_materials|review_material_gaps|select_pns|verify_selections|review_open_items), compatibility, orderable}` (derived progress only; null component counts mean no proposal); `unresolved_details?[] {code, message, next_action}`; `workflow?`; `messages?[]`.
