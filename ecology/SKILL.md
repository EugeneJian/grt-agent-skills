---
name: ecology
description: Browse Growatt products, select one inverter by market and rated kW or one accessory unit by market and model, or configure systems through the Ecology API or MCP. Default to product information and component quantities; query or verify PN only when explicitly requested. Does not place orders, manage API Keys or maintain the server.
---

# Ecology

Answer at the depth asked — a product list, model facts, single-unit alternatives or a system proposal — from the connected Ecology service. The service owns the contract, catalog, rules, quantities and candidates. This Skill only says how to connect, what to discover, and the few judgments the API cannot make for you.

## Connect

- **HTTP API** (default): `https://ecology.growatt.com/api/v1/ecology`.
- **Cloud MCP** (Streamable HTTP): `https://ecology.growatt.com/api/v1/ecology/mcp`. Use it when it is the chosen connection or no API credential is configured.
- Send `Authorization: Bearer` with an application Key from the host's secret environment or a host-managed employee OAuth token. Never put a credential in a URL, file, command argument or output.
- Keep the connection and identity already chosen for the task. Do not extract an MCP token for HTTP, create a Key to change route, or switch identity after a denial.
- Host setup and the Key-versus-OAuth choice: [connection](references/connection.md).
- Send a descriptive `User-Agent` on HTTP. A plain-text 403 `error code: 1010` is an edge block of the client signature, not a credential problem: set a `User-Agent` and retry once.

## Discover; do not assume

Nothing below is copied into this Skill; read it from the service each task and reuse identical results within the task.

| Need | Source |
| --- | --- |
| Contract version | `X-Ecology-API-Version` response header |
| Operations, paths, MCP tool names, scopes, required inputs and availability for this credential | `GET /portfolio` → `endpoints` (only call it when grants or operations are unknown) |
| What can be done next for one product in one market, and why not | `GET /products/{product}` → `next_actions` and their `status` |
| Calculation inputs, schemes, bounds and selectable components | `GET /products/{product}/rules` → `schemes[].rule_block` and `components` |
| Field errors | 400 `error.issues` paths; correct every listed field before resending |
| Routing guidance and workflow (MCP) | Server instructions, then the `ecology://workflow` resource once per task; read `ecology://workflow/materials` or `ecology://workflow/plug-in` only when the task needs them |

Over HTTP there is no workflow resource. Follow `next_actions`, returned rule admission and evaluator results. If a decision needs the workflow text itself, connect the cloud MCP; never substitute a repository copy. A capability the service does not advertise does not exist for this credential: report the gap rather than inventing parameters or scanning the catalog.

## Judgments the API cannot make for you

- **Depth.**
  - Information and component quantities are the default.
  - Query materials, set `resolve_materials`, or verify PNs only when the user explicitly asks for PNs or material codes. A BOM request alone does not imply PN work.
- **One exact market per request.**
  - Use market-wide model search (`market_models`) or a search within one market, never a catalog-wide scan.
  - A product missing from a market's `products` list has no current PN there. That is not a sales decision.
  - `authorized_markets` are the credential's grants. A card's `selectable_markets` are where it can be selected; choose configuration and PN markets only from those.
- **Single units.** `unit_only` or `inverter_only` rows (the latter with exact `power_kw`) are separate quantity-one alternatives, not BOM lines. Present them; do not pick one for the user.
- **Origin (COO).** Is separate from the sales market. For explicitly requested PN work, follow the workflow's COO default and state it; never infer origin from market or PN prefix.
- **Pins.**
  - Copy `version`, `rules_version` and `sku_version` from reads of the same product and market, unchanged.
  - Copy a candidate's complete `selection` when you reuse it.
  - On 409, reread the resources in `error.recovery.stale` and review what changed before evaluating again.
- **Conditional components.** Unknown meter ownership is not "already installed". Keep unresolved components named, not dropped.
- **Result boundaries.**
  - `compatibility: unknown` and `orderable: false` stay as returned.
  - `confirmed` means a current candidate match, not certification, stock or order approval.
  - Card EOL is known only when `meta.lifecycle_source` is `sku_projection`.

## Errors

- Branch on `error.code`, then `error.reason`; never parse prose. Act on `error.next_action`.
- Retry only when `error.retryable` is true, after `Retry-After`, with unchanged inputs and pins. Otherwise report the code and `request_id`.
- 403 `scope_missing` or `market_not_granted` needs an administrator grant. 404 `market_not_available` means choose a market from portfolio.
- On 429, report `Retry-After` and stop the current batch.

Example, one Australian market overview: `ecology_market_models({"market":"AU"})` over MCP, or `GET /market-models?market=AU` over HTTP.
