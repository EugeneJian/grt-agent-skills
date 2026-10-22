# Maintained sources and transport

Read this when the canonical workflow needs a reference, when only HTTP is available, or when a local checkout is unavailable.

## Ownership

| Owner | Role |
| --- | --- |
| `EugeneJian/grt-agent-skills`, `ecology/` | Portable `$ecology` discovery entry and source routing; no product-rule copy |
| `EugeneJian/AI-Copilot`, `applications/cockpit/tools/ecology-mcp/skills/ecology-configurator/SKILL.md` | Maintained configuration workflow, also exposed by the matching cloud/local MCP server as `ecology://workflow` |
| Connected Ecology service | Authorized current catalog, published rules, material resolver, candidates and verification |

The user-level folder is the one local copy of this entry. Tool-specific entries link to it. Do not copy the canonical workflow into this folder: update its owner in AI-Copilot when the workflow needs changing. GitHub publication, local installation and production server deployment are separate states.

## Read only the needed reference

Paths below are relative to an AI-Copilot checkout or its [GitHub repository](https://github.com/EugeneJian/AI-Copilot). Pin a fetched revision when using several related documents.

| Need | Authoritative path |
| --- | --- |
| Workflow | [`applications/cockpit/tools/ecology-mcp/skills/ecology-configurator/SKILL.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/tools/ecology-mcp/skills/ecology-configurator/SKILL.md) |
| COO default and source scope | [`docs/products/ecosystem-rules/README.md#coo-configuration-preference`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecosystem-rules/README.md#coo-configuration-preference) |
| Meter requirement details | [`docs/products/ecosystem-rules/smart-meter-selection.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecosystem-rules/smart-meter-selection.md) |
| Request fields and response semantics | [`applications/cockpit/docs/ecology-api.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-api.md) and its adjacent `ecology-openapi.json` |
| Cloud MCP quickstart and HTTP examples | [`applications/cockpit/docs/ecology-third-party-testing.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-third-party-testing.md) |
| Employee OAuth sign-in | [`applications/cockpit/docs/ecology-mcp-oauth.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-mcp-oauth.md) |
| Transport contract and optional adapter | [`applications/cockpit/tools/ecology-mcp/README.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/tools/ecology-mcp/README.md) |
| Known release/acceptance limits | [`docs/products/ecology-current-status.md`](https://github.com/EugeneJian/AI-Copilot/blob/main/docs/products/ecology-current-status.md) |

A GitHub document may lag a directly deployed local release. Use the matching supplied contract or checkout when available; live discovery and validation still decide supported operations. Report a material mismatch instead of fabricating parameters. A document that is inaccessible is not evidence that its business requirement is absent.

## Cloud setup for Codex and Pi

The [maintained quickstart](https://github.com/EugeneJian/AI-Copilot/blob/main/applications/cockpit/docs/ecology-third-party-testing.md#1-cloud-mcp-quickstart) owns the exact configuration snippets. With the known AI-Copilot checkout, read that file locally when it is newer than GitHub. The [Feishu guide](https://q02gj5lyidv.feishu.cn/wiki/UxglwhNPzi6lMek0kmvcZZn9nLf) is its online reading copy.

| Host | Employee setup |
| --- | --- |
| Codex | Set the Ecology entry in `~/.codex/config.toml` to the cloud URL and `auth = "oauth"`; run `codex mcp login ecology`, complete Feishu consent, then restart the running session. |
| Pi | Set the Ecology `mcpServers` entry in `~/.pi/agent/mcp.json` to the cloud URL; run `pi mcp login ecology`, complete Feishu consent, then `/reload` or restart. |

Employee entries have no local command, custom Authorization header or Key environment binding. Preserve other servers and check for a stale project-level Ecology override. Host-native OAuth stores and refreshes credentials; do not copy credentials into the Skill. The Skill is guidance, not an installed connector or a grant.

Third parties retain an independently supplied Key. Both CLIs support `mcp add ecology-partner --url https://feishu.myshine.online/api/v1/ecology/mcp --bearer-token-env-var ECOLOGY_API_TOKEN`, prefixed with `codex` or `pi`. Use the host's secret launch environment, then reload/restart; no OAuth login is required for that Key connection. If both connections exist, preserve the explicitly selected identity. Never substitute a Key after OAuth denial.

If sign-in needs renewal, report it once. An old browser session without enterprise identity needs fresh company Feishu login; persistent denial goes to the integration contact. Do not bypass enterprise checks or reuse a lark CLI token. After setup, an Australia overview uses `ecology_market_models({"market":"AU"})` once, without PN lookup; initialization/discovery/resource reads are separate connection requests.

## Transport equivalence

The cloud Streamable HTTP MCP endpoint is `https://feishu.myshine.online/api/v1/ecology/mcp`. Employee OAuth is the preferred mode: connect from an OAuth-capable host, leave a custom API Key header empty, and follow the host's sign-in flow. The host manages refresh; the Skill neither reads browser Cookies nor uses lark CLI credentials. Check the release status for actual deployment/acceptance.

Third-party integrations can use an existing API Key with cloud MCP or HTTPS API. The local stdio adapter remains only for an explicitly chosen stdio-only host. This remains an explicit connection choice, not an automatic fallback after OAuth failure. OAuth access tokens are audience-bound to cloud MCP and cannot authenticate the public HTTP Key routes. All supported transports reach the same Ecology operations; authentication does not change the configuration rules.

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

For Key mode, keep an existing API Key in the host's secret environment. Never include it in the Skill, generated artifacts, URLs, console output or chat. Do not print a full MCP configuration or credential store while checking whether a connection exists. Connection setup is separate from a request to propose a system.
