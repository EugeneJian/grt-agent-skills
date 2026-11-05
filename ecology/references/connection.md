# Connection

Read this only to set up a host or choose between a Key and employee OAuth. Operations, inputs and the contract version come from the service itself (see [Discover; do not assume](../SKILL.md#discover-do-not-assume)).

## Ownership

| Owner | Role |
| --- | --- |
| `EugeneJian/grt-agent-skills`, `ecology/` | This portable entry: connection and discovery routing, no product rules |
| The connected Ecology service | Sole runtime source: contract, catalog, rules, quantities, candidates, verification and the `ecology://workflow` resource |
| `EugeneJian/AI-Copilot` | Maintains the service and its workflow; maintainer background, never loaded during a task |

## Routes and identities

| Route | Identity |
| --- | --- |
| HTTP API `https://ecology.growatt.com/api/v1/ecology` (default) | Application Key in the host's secret launch environment (for example `ECOLOGY_API_TOKEN`), or an employee OAuth token the host manages for the shared Ecology resource |
| Cloud MCP `https://ecology.growatt.com/api/v1/ecology/mcp` | Employee OAuth through the host's sign-in flow, or a third party's own Key |

Both routes reach the same operations; authentication never changes configuration rules. Keep the route and identity selected for the task. A host holding only an MCP connection has no HTTP access, and its tokens must not be extracted. Never use a Key as a fallback after an OAuth denial.

## Host setup

The [Feishu guide](https://q02gj5lyidv.feishu.cn/wiki/UxglwhNPzi6lMek0kmvcZZn9nLf) holds the maintained quickstart snippets for both routes.

| Host | Employee setup (cloud MCP, OAuth) |
| --- | --- |
| Codex | Set the Ecology entry in `~/.codex/config.toml` to the cloud MCP URL; run `codex mcp login ecology`, complete Feishu consent, then restart the session |
| Pi | Set the Ecology `mcpServers` entry in `~/.pi/agent/mcp.json` to the cloud MCP URL; run `pi mcp login ecology`, complete Feishu consent, then `/reload` |

Employee entries have no local command, custom Authorization header or Key binding; the host stores and refreshes OAuth. Sign in from a browser profile in the configured enterprise; another profile can return `access_denied`. If sign-in fails, report it once to the integration contact; do not bypass enterprise checks or reuse other CLI tokens.

Third parties keep their own Key: `codex mcp add ecology-partner --url https://ecology.growatt.com/api/v1/ecology/mcp --bearer-token-env-var ECOLOGY_API_TOKEN` (or the same with `pi`), with the Key in the host's secret launch environment. Never print a full MCP configuration or credential store while checking whether a connection exists.

Installing this Skill does not install a connector, create a Key or grant access.
