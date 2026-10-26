---
name: ecology
description: Browse Growatt products and models or configure systems through the Ecology API or MCP. Default to product information and component quantities; query or verify PN only when explicitly requested. Does not place orders, manage API Keys or maintain the server.
---

# Ecology configuration

Answer at the requested depth from current Ecology results: a product list, model information, or a system proposal. Load the deployed workflow from the connected service before choosing defaults or querying materials. This entry point owns skill discovery and routing; it does not own product rules, PN-to-factory mappings or quantities.

## Choose the connection once

Default to the direct HTTP API at `https://feishu.myshine.online/api/v1/ecology`: it is the primary route for team use. The host manages an authorized application Key (for example `ECOLOGY_API_TOKEN` in its secret environment) or an employee OAuth Bearer token for the shared Ecology resource. Call its HTTP paths without MCP tool or resource discovery; [Sources and transport](references/sources.md) maps the same nine operations, documents each endpoint's capability, scope and inputs, and links the field-level [API schema](references/api-schema.md). Use the cloud Streamable HTTP endpoint `https://feishu.myshine.online/api/v1/ecology/mcp` only for an explicitly chosen MCP connection or when direct API access is not configured.

Preserve an explicit connection or authentication choice. Otherwise use an existing authorized direct API integration first; if none exists, reuse an existing employee Feishu OAuth cloud MCP connection or follow the [cloud setup](references/sources.md#cloud-setup-for-codex-and-pi). Use only a credential already authorized for the selected route. Do not extract tokens from an MCP host for HTTP API, create or retrieve a Key merely to change transport, or switch identities after a denial. Identify the mode from non-secret host connection metadata and state it once; a tool name or successful response alone does not prove OAuth.

If the selected route needs setup or renewed sign-in, report that requirement once using the [connection reference](references/sources.md); do not silently switch credentials or routes. Let the host refresh OAuth normally. Do not repeatedly ask for an authentication choice on each operation, change host credentials, or switch identities after a grant denial. Keep the same authorized connection for the task.

## Load the workflow once

The connected service is the only workflow source; never load it from a Git repository or local checkout.

1. With a connected cloud Ecology MCP server, read its `ecology://workflow` resource once per task and keep the returned revision. It is the deployed workflow matching the live catalog and rules.
2. In direct API mode there is no workflow resource over HTTP. Route from this entry, and treat live service evidence — `GET /products/{product}/rules`, returned `rule_admission`, evaluator results and derived material fields — as authoritative. If a decision needs the deployed workflow text itself, connect the cloud MCP server; do not substitute a repository copy.

[Sources and transport](references/sources.md) maps the HTTP/MCP operations and each endpoint's capability. Do not combine contradictory editions or silently fall back to old rules. If entry routing plus live results are insufficient for a configuration decision, report that gap; do not invent a completed configuration. Live API capabilities, returned rule admission and current candidates determine what can actually execute. A workflow document cannot enable a feature or authorize a source change.

## Match the request before querying

Follow the loaded workflow's task-depth routing. A simple product/model question must not become a full configuration or a catalog-wide model scan. Default to information and component quantities. Call material lookup, enable material resolution or verify PNs only when the user explicitly requests PN/material codes or a BOM containing them; an ordinary BOM request does not imply PN work. Do not ask about COO, meter ownership or PN choices for a catalog overview.

Reuse same-input, same-version results within the task, including empty lists. For a country/market model list, call `GET /market-models` with the exact market in API mode, or `ecology_market_models` in MCP mode; no portfolio or per-card scan is needed. A returned catalog card is not proof of model availability; a selectable model is not certification or sales approval. If the connected service lacks the batch operation, report that gap rather than scanning every card. Stop the current batch on 429; do not wait and resume a broad scan by default.

## Capture configuration intent

- Preserve the requested product, sizing, market and prior PN choices. Ask only for missing decisions that materially change the configuration and have no documented default.
- Keep **use/supply market** and **COO/manufacturing origin** separate. For explicitly requested PN work, apply the documented origin default — China (Huizhou), requested as `coo: "CN"`; use `coo: "VN"` only when the customer explicitly requests the Vietnam factory or Vietnam COO — before requesting candidates, and disclose it in the result. Do not query all origins as a substitute for the default or infer COO from the sales market or PN prefix. An explicitly requested all-origin comparison remains a comparison, not a selected factory.
- Keep the two market scopes separate. `authorized_markets` only lists the credential's grants; a card's `selectable_markets` is where its current materials support selection. Choose the configuration and PN market from `selectable_markets`, and report a granted market outside it as having no selectable model. If a response has no `selectable_markets` (older contract or `null`), confirm the market with `models` or `market-models` instead of treating a grant as selectable.
- Treat country-specific and regional markets as separate scopes. If a destination alone leaves two intended supply scopes plausible, resolve that business choice; do not automatically merge or substitute them.
- Use only the discovery and rule resources needed for the request, then evaluate supported quantities when configuring. Model-list responses carry SKU versions for paging; discovering those versions does not request PN work. Choose PNs and revalidate candidates only for explicitly requested material work. Quantities and eligibility come from the evaluator; never reproduce its business rules in the model.
- Pass the same market, origin/preferences, sizing and version pins through evaluation and revalidation. Copy a candidate's complete `selection` when exposed. Do not transform its `country`, nameplate or PN.
- For meters and other conditional components, use the returned requirement and the customer's actual ownership/needs. Unknown ownership is not “already installed”; an unconfirmed installation detail is not permission to omit a required role. Keep supported components available while naming the remaining decision.
- Keep pending/expired evidence and missing PN mappings local to their affected components. An empty main-model set can still carry a usable SKU version for component evaluation; inspect returned status rather than declaring the entire product unsupported.

## Present the result for a decision

Follow the canonical presentation contract. For configuration, give a compact requirement summary and a component table with model/specification, quantity, supply and next action. Include PN and COO evidence only for explicitly requested material work; browsing needs only a concise product/model list. Retain included and customer-supplied lines without counting them as separate purchases. Multiple candidates share one component quantity.

Distinguish a requested/default COO filter from verified component COO. If origin evidence is missing, label that component unresolved even when a default was requested. Do not use a remembered factory-to-PN mapping or choose the first of several candidates without a supported preference.

Card `lifecycle.is_eol` is card-level EOL. Report it as known only when `meta.lifecycle_source` is `sku_projection`; otherwise say EOL is unknown rather than active. PN material status (`Z4`, `Z1`) and one discontinued nameplate are not card EOL. Use returned progress, unresolved explanations and selection checks. State exactly which PNs were revalidated; `confirmed` is a current candidate match, not compatibility, certification, stock or order approval. Preserve `compatibility: unknown` and `orderable: false` when returned. Keep version pins and request IDs available, and revalidate close to downstream use.

## Access and recovery

Use existing authorized API/MCP credentials without printing them. Direct HTTP calls use `Authorization: Bearer` with an application Key from the host secret environment or a host-managed employee OAuth token for the shared Ecology resource. Never place credentials in a URL, Skill file, command argument or output. A Skill does not configure credentials or grant access. If the chosen route is unavailable, use the setup reference and report the missing dependency; never scrape the Key administration UI or create a test Key automatically.

Branch on `error.code`, then on `error.reason` when returned; never parse prose. For rejected inputs, correct the fields named in `error.issues` paths. A 403 `scope_missing` or `market_not_granted` needs an administrator grant; a 404 `market_not_available` means choose a market returned by portfolio; `unknown_endpoint` means a wrong path. Retry only when `retryable` is true, after `Retry-After`, with unchanged inputs and pins; otherwise report the code and `request_id`. On a version conflict, refresh the indicated resources and review changed facts before repeating the evaluation; do not merely replace hashes. Keep partial results honest. For OAuth expiry, let the host refresh or request renewed sign-in once; grant failures and Key issues require the existing integration contact. On a rate limit, report Retry-After and stop the current batch; do not automatically resume a broad scan. No personal saved selection, order, deployment or remote write is implied by a configuration request.
