# Ecology API schema (service-derived)

Field-level contract for the nine operations, transcribed from the connected service's own operation contract; the HTTP API and the cloud MCP tools expose the same shapes. The live service is authoritative: on any mismatch, trust the service response and report the drift so this file can be updated. Capture: 2026-10, deployed cloud service.

## Common conventions

- Base `https://feishu.myshine.online/api/v1/ecology`; auth `Authorization: Bearer <Key or employee OAuth token>`. Never place credentials in URLs or output.
- Exact market codes: `AE AT AU BE BG BR CA CH CL CN CO CY CZ DE DK EE ES FI FR GB GE GR HR HU IE IL IN IQ IS IT JP KR LT LU LV MT MX NA NG NL NO NZ PH PK PL PT RO SA SE SI SK TH TW US VN ZA`, plus regional `EUROPE` and `GENERIC`. `GLOBAL` is browsing-only.
- Version pins are 64-char hex: `version` (catalog) and `sku_version` (SKU projection). Carry them across pages and into follow-up calls; `offset > 0` on model endpoints requires `sku_version`.
- Pagination: `limit` defaults to and maxes at 4000; `offset` 0–10000; pages are bounded to 2 MiB (`meta.page_limited_by_bytes` marks a byte-truncated page; advance to `meta.offset + meta.limit`). A single oversized row returns 413 `response_too_large`.
- Envelope: `{ "data": …, "meta": …, "request_id": <uuid> }`. Common `meta`: `generated_at`, `expires_at`, `language` (`en`/`zh-CN`), `version`, `rules_version {data, engine, runtime}`, `market_context? {kind, market, message, automatic_market_merge: false, approval: "not_assessed"}`, and for paged reads `total`, `offset`, `limit`, `requested_limit?`. Model-returning reads add `sku {version, expires_at}` and `models_status` (`ok`/`empty`).
- Errors: 400 field-level issues; 401/403 credential or grant boundary; 404 unknown id; 409 version conflict → read `error.recovery.stale`, refresh indicated resources, review changed facts; 413 single row too large (request less detail); 429 stop the batch and honor `Retry-After`; 503 report the unavailable dependency.

## GET /portfolio (`ecology_portfolio`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum \| `all` \| string \| null | Omitted/null/blank/`all` = all authorized markets. |
| `version` | 64-hex | Optional pin. |

Response `data`: `endpoint_access_meaning` (scope only); `endpoints[] {available, method, operation, path, required_inputs[], required_scopes[], tool}`; `market`; `markets[] {code, name}`; `product_count`; `products[] {id, name, categories[] {id,name}, capabilities[], lifecycle {is_eol, is_new}, markets[]?, calculation_status, documentation_status}`. No pagination.

## GET /products (`ecology_products`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum \| `all` | Optional discovery scope. |
| `search` | string ≤100 | Optional text search. |
| `capability` | enum | `New` \| `VPP` \| `Smart scheduling` \| `ShinePhone2.0` \| `Grominder` (Chinese values retained as legacy aliases). |
| `offset` / `limit` | int | See pagination. |
| `version` | 64-hex | Optional pin. |

Response `data[]`: `id` (`[A-Za-z0-9_-]{1,80}`), `name`, `image_url`, `categories[]`, `capabilities[]`, `lifecycle {is_eol, is_new}`, `markets[]?`, `url`, `rule_coverage {calculation {status: partial|not_implemented|unavailable|market_required, kind, bounds?, schemes?}, documentation {status: available|not_recorded}}`.

## GET /market-models (`ecology_market_models`)

| Param | Type | Notes |
| --- | --- | --- |
| `market` | enum | **Required**, exact market. |
| `search` | string ≤100 | Matches products/aliases/nameplates. |
| `offset` / `limit` | int | `offset > 0` requires `sku_version`. |
| `version`, `sku_version` | 64-hex | Pins. |

Response `data[]`: `product_id`, `product_name`, `nameplate`, `power_kw` (number \| null), `countries[]` (exact labels), `country_options[]? {country, country_label?, market_code?}`.

## GET /products/{product} (`ecology_product`)

| Param | Type | Notes |
| --- | --- | --- |
| `product` | path, `[A-Za-z0-9_-]{1,80}` | From discovery; never invent ids. |
| `market` | enum | **Required**, exact market. |
| `version` | 64-hex | Optional pin. |

Response `data`: card fields as `/products`, plus `rule_coverage.calculation.bounds? {battery_min, battery_max, module_kwh, cluster_count? (1–3), max_clusters?, phase, powers_kw[], scheme_id?}` and `schemes?[]` of the same shape.

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
| `offset` / `limit` | int | `offset > 0` requires `sku_version` (and `version`). |
| `version`, `sku_version` | 64-hex | Pins. |

Response `data[]`: `nameplate`, `power_kw`, `countries[]`, `country_options[]?`. `meta` adds `sku {version, expires_at}`, `models_status` (`ok`/`empty`); an empty list is a successful result.

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
| `offset` / `limit`, `version`, `sku_version` | — | As above; `offset > 0` needs both pins. |

Response `data[]`: `pn`, `nameplate`, `country`, `country_label?`, `market_code?`, `status: Active|Z4`, `coo?` (CN|VN|null, with details), `specification?`, `description?`.

## POST /configurations/evaluate (`ecology_evaluate`)

Request body (JSON):

| Field | Type | Notes |
| --- | --- | --- |
| `product`, `market` | string / enum | Exact market. |
| `scheme_id` | string | When the product exposes schemes. |
| `phase` | `single` \| `three` | Standard families; from rule bounds. |
| `power_kw`, `capacity_kwh` | number > 0 | Standard sizing; use values from rule bounds/schemes (`powers_kw`, `module_kwh` multiples). Misaligned sizing returns `no_match` / `outside_coverage`. |
| `has_meter` | bool | MINA: omit when meter ownership is unknown. |
| `component_ids` | string[] | Optional selectable components from rules. |
| `balcony` | object | NOAH/NEXA/AURA: `{channel: "offline", scenario?, values {key: number}, accessories?[]}` from rules; replaces phase/power/capacity. |
| `resolve_materials` | bool | Explicit PN work only; needs `materials:read`. |
| `coo` | `CN` \| `VN` \| `all` | With `resolve_materials`. |
| `version` | 64-hex | **Required** for standard families (balcony families send `balcony` instead): catalog pin from the preceding read. |
| `rules_version` | object | **Required** together with `version`: the full `meta.rules_version` object `{data, engine, runtime}` copied from the same read. A bare hash string is rejected. |
| `sku_version` | 64-hex | Only with `resolve_materials: true`; from `models`. |
| `component_selections` | array | Stateless revalidation: `{component_id, pn, nameplate, country}` copied from chosen candidates. |

Response `data`: `status: technical_reference|pending_rules|coming_soon|no_match`; `evaluation {calculation: executed_partial|not_implemented|not_evaluated|outside_coverage, compatibility: "unknown", orderable: false}`; legacy `configurations[] {capacity_kwh?, items[] {role, quantity|null, unit, material?}}`; `proposal?` `{schema_version: 1, status: "draft", market, product, rule {id, version}, inputs, lines[] {id, component_id, role, name, quantity|null, unit, supply: separate|included|optional|external, review_status: "pending_review", rule_version, material {candidates[] {pn, nameplate?, country?, country_label?, market_code?, specification?, description?, status?, selection?}, source: D1_material_backup|Feishu_accessory_binding|null, status, binding?}}, meter? {requirement, status}, performance?, topology? {nodes[], edges[]}, unresolved[]}`; `selected_accessories[]?`; `selection_verification? {checked_at, scope: "current_component_candidates_only", checks[] {component_id, selection {pn, nameplate, country}|null, status: confirmed|pending|needs_review|unverified}}`; `rule_admission?`; `checks?[]`; `summary?` (progress counts only); `unresolved_details?[] {code, message, next_action}`; `workflow?`; `messages?[]`.
