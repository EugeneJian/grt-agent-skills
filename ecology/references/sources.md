# Maintained sources and transport

Read this to choose the connection, review ownership, or check each endpoint's capability and scope. Runtime work uses only the connected service: the direct HTTP API first, cloud MCP as fallback, and `ecology://workflow` as the deployed workflow.

## Ownership

| Owner | Role |
| --- | --- |
| `EugeneJian/grt-agent-skills`, `ecology/` | Portable `$ecology` discovery entry and source routing; no product-rule copy |
| Connected Ecology service | Sole runtime source: authorized catalog, published rules, material resolver, candidates, verification, and the deployed workflow exposed as `ecology://workflow` |
| `EugeneJian/AI-Copilot` repository | Maintains the deployed Ecology service and its workflow; maintainer reference only, never a runtime source for tasks |

The user-level folder is the one local copy of this entry. Tool-specific entries link to it. Do not copy the workflow into this folder: changes belong to the service owner in AI-Copilot. GitHub publication, local installation and production server deployment are separate states; only the connected service reflects production.

## Maintainer reference (not runtime sources)

Runtime tasks use only the connected service: the HTTP API endpoints below and, over MCP, the deployed `ecology://workflow` resource. The paths below are maintainer background relative to the [AI-Copilot repository](https://github.com/EugeneJian/AI-Copilot); agents must not load them during tasks.

| Need | Authoritative path |
| --- | --- |
| Workflow | [`applications/cockpit/tools/ecology-mcp/skills/ecology-configurator/SKILL.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/tools/ecology-mcp/skills/ecology-configurator/SKILL.md) |
| COO default and source scope | [`docs/products/ecosystem-rules/README.md#coo-configuration-preference`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecosystem-rules/README.md#coo-configuration-preference) |
| Meter requirement details | [`docs/products/ecosystem-rules/smart-meter-selection.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecosystem-rules/smart-meter-selection.md) |
| Request fields and response semantics | [`applications/cockpit/docs/ecology-api.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-api.md) and its adjacent `ecology-openapi.json` |
| Cloud MCP quickstart and HTTP examples | [`applications/cockpit/docs/ecology-third-party-testing.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-third-party-testing.md) |
| Employee OAuth sign-in | [`applications/cockpit/docs/ecology-mcp-oauth.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-mcp-oauth.md) |
| Cloud MCP registration and API/Skill contract | [`applications/cockpit/tools/ecology-mcp/README.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/tools/ecology-mcp/README.md) |
| Known release/acceptance limits | [`docs/products/ecology-current-status.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecology-current-status.md) |

A repository document may lag the deployed release; live discovery and validation decide supported operations. Report a material mismatch instead of fabricating parameters. A document that is inaccessible is not evidence that its business requirement is absent.

## Cloud setup for Codex and Pi

The [Feishu guide](https://q02gj5lyidv.feishu.cn/wiki/UxglwhNPzi6lMek0kmvcZZn9nLf) holds the maintained quickstart snippets: cloud MCP configuration and HTTP examples for both routes.

Direct HTTP API is the default team route: provision each host with an application Key for the shared Ecology resource in its secret launch environment (for example `ECOLOGY_API_TOKEN`) and send `Authorization: Bearer` to the API base below; see [API endpoint capabilities](#api-endpoint-capabilities). No MCP registration, OAuth login or tool discovery is required. Cloud MCP below is the fallback when direct API access is not configured; a host holding only an MCP connection has no direct API access, and its tokens must not be extracted for HTTP calls.

| Host | Employee setup |
| --- | --- |
| Codex | Set the Ecology entry in `~/.codex/config.toml` to the cloud URL; run `codex mcp login ecology`, complete Feishu consent, then restart the running session. |
| Pi | Set the Ecology `mcpServers` entry in `~/.pi/agent/mcp.json` to the cloud URL; run `pi mcp login ecology`, complete Feishu consent, then `/reload` or restart. |

Employee entries have no local command, custom Authorization header or Key environment binding. Preserve other servers and check for a stale project-level Ecology override. Host-native OAuth stores and refreshes credentials; do not copy credentials into the Skill. The Skill is guidance, not an installed connector or a grant.

Third parties retain an independently supplied Key. Both CLIs support `mcp add ecology-partner --url https://feishu.myshine.online/api/v1/ecology/mcp --bearer-token-env-var ECOLOGY_API_TOKEN`, prefixed with `codex` or `pi`. Use the host's secret launch environment, then reload/restart; no OAuth login is required for that Key connection. If both connections exist, preserve the explicitly selected identity. Never substitute a Key after OAuth denial.

Complete authorization in a browser signed into the configured enterprise. An unrelated browser profile can return `access_denied` even while another profile has a valid employee session. If sign-in fails, report it once to the integration contact. Do not bypass enterprise checks or reuse a lark CLI token. With an authorized direct API integration, an Australia overview uses `GET /market-models?market=AU` once, without PN lookup. In MCP mode, use `ecology_market_models({"market":"AU"})`; initialization, discovery and resource reads are separate connection requests.

## Transport equivalence

The direct HTTP API base is `https://feishu.myshine.online/api/v1/ecology`; it accepts an application Key or a new employee OAuth token for the shared Ecology resource. The cloud Streamable HTTP MCP endpoint is `https://feishu.myshine.online/api/v1/ecology/mcp`. For employee access, connect from an OAuth-capable host, leave a custom API Key header empty, and follow the host's sign-in flow. The host manages refresh; the Skill neither reads browser Cookies nor uses lark CLI credentials. The connected server's own responses and returned rule admission show actual deployment/acceptance.

For Skill-guided work, prefer direct HTTPS API when the host already manages an authorized Key or employee OAuth token for that route. Otherwise use an existing cloud MCP OAuth connection, or a separately granted third-party Key connection, when selected. There is no local stdio adapter. Preserve the selected route and identity; do not use a Key as an automatic fallback after OAuth failure. All supported transports reach the same Ecology operations; authentication does not change the configuration rules.

| MCP tool | HTTP resource, relative to the configured API base |
| --- | --- |
| `ecology_portfolio` | `GET /portfolio` |
| `ecology_products` | `GET /products` |
| `ecology_market_models` | `GET /market-models` (exact market; no PN lookup) |
| `ecology_product` | `GET /products/{product}` |
| `ecology_description` | `GET /products/{product}/description` |
| `ecology_rules` | `GET /products/{product}/rules` |
| `ecology_models` | `GET /products/{product}/models` |
| `ecology_materials` | `GET /products/{product}/materials` |
| `ecology_evaluate` | `POST /configurations/evaluate` |

For direct API or Key-authenticated cloud MCP, keep an existing API Key in the host's secret environment; an OAuth-capable HTTP host must manage employee token acquisition, secure storage and refresh. Never include it in the Skill, generated artifacts, URLs, console output or chat. Do not print a full MCP configuration or credential store while checking whether a connection exists. Connection setup is separate from a request to propose a system.

## API endpoint capabilities

All paths are relative to the API base `https://feishu.myshine.online/api/v1/ecology`; the MCP column names the equivalent cloud tool. Paginated endpoints accept at most 4000 rows per page and bound pages to 2 MiB: advance to `meta.offset + meta.limit`, preserve `meta.version` and `meta.sku.version`, and reconcile all pages before claiming complete coverage. An empty list is final for the snapshot, not a retry signal. Material availability retains Active/blank and Z4 while always excluding Z1. Stop the current batch on 429 and respect Retry-After.

| HTTP | MCP tool | Capability | Required scope | Key inputs |
| --- | --- | --- | --- | --- |
| `GET /portfolio` | `ecology_portfolio` | Discover markets, products and follow-up operations authorized to this credential; aggregate coverage stays `market_required` and is browsing only. | `catalog:read` | `market` optional; omitted/`all` lists all authorized markets. |
| `GET /products` | `ecology_products` | Search and page authorized product cards (categories, capabilities, lifecycle, rule coverage). A catalog card is not proof of local model availability. | `catalog:read` | `market`, `search`, `capability` optional; `offset`/`limit`. |
| `GET /market-models` | `ecology_market_models` | One request listing selectable models (nameplate, power, exact country labels) for one exact market, using shared Web availability. Selectable is not sale, certification or order approval. | `catalog:read` | Exact `market` required; `search` optional; `offset > 0` needs `sku_version`. |
| `GET /products/{product}` | `ecology_product` | One product's markets, documentation status and calculation coverage/bounds. | `catalog:read` | `product` ID from discovery. |
| `GET /products/{product}/description` | `ecology_description` | Product introduction, features and official source links; prose is not market approval. | `catalog:read` | `product`; `locale` `en`/`zh-CN`. |
| `GET /products/{product}/rules` | `ecology_rules` | Published configuration rules, sizing bounds and balcony scenarios/accessories; check rule admission before evaluating. | `catalog:read` | `product`. |
| `GET /products/{product}/models` | `ecology_models` | Selectable nameplates for one product and market; returns `meta.sku.version` for later material work; an empty list is successful. | `catalog:read` | `product`, exact `market`; continuation needs `version` and `sku_version`. |
| `GET /products/{product}/materials` | `ecology_materials` | Resolve candidate PNs for one exact nameplate and country label. Use only for explicitly requested PN work; candidates are not a BOM. | `materials:read` | `product`, `market`, `nameplate`, `country`; `coo` `CN`/`VN`/`all` plus detail flags; carry `version`/`sku_version`. |
| `POST /configurations/evaluate` | `ecology_evaluate` | Component quantities and Proposal lines through the shared Web engine, including reviewed balcony scenes; stateless PN revalidation via `component_selections`. | `configuration:evaluate`; `materials:read` when `resolve_materials: true` | Scheme plus `phase`/`power_kw`/`capacity_kwh` or `balcony`; catalog and rules version pins. |

Field-level request/response schemas for all nine endpoints: [API schema](api-schema.md), transcribed from the deployed service's own operation contract; the live service is authoritative on mismatch.
