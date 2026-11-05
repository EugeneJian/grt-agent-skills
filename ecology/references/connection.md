# Connection

Read this only to set up a host or choose between a Key and employee OAuth. The workflow, operations, inputs and contract version come from the service itself (see [the workflow](../SKILL.md#then-read-the-workflow-from-the-service)).

## Ownership

| Owner | Role |
| --- | --- |
| `EugeneJian/grt-agent-skills`, `ecology/` | This portable entry: connection and discovery routing, no product rules |
| The connected Ecology service | Sole runtime source: workflow (`GET /workflow` or `ecology://workflow`), contract, catalog, rules, quantities, candidates and verification |
| `EugeneJian/AI-Copilot` | Maintains the service and its workflow; maintainer background, never loaded during a task |

## Environments and identities

| Environment | HTTP API | Cloud MCP server | Identity |
| --- | --- | --- | --- |
| GA (default) | `https://ecology.growatt.com/api/v1/ecology` | `ecology` → `https://ecology.growatt.com/api/v1/ecology/mcp` | Company application Key `ECOLOGY_API_TOKEN`, or employee OAuth for the company resource |
| Latest | `https://feishu.myshine.online/api/v1/ecology` | `ecology-latest` → `https://feishu.myshine.online/api/v1/ecology/mcp` | Latest application Key `ECOLOGY_LATEST_API_TOKEN`, or employee OAuth for the latest resource |

Each environment has its own Platform, grants, quotas and OAuth resource; Keys and tokens are issued and revoked separately, so keep them in separate secret variables and MCP entries. Both reach the same operations, but versions and data can differ until Latest is promoted to GA. Authentication never changes configuration rules. Keep the environment, route and identity selected for the task. A host holding only an MCP connection has no HTTP access, and its tokens must not be extracted. Never use a Key, or the other environment, as a fallback after a denial.

## Host setup

The [Feishu guide](https://q02gj5lyidv.feishu.cn/wiki/UxglwhNPzi6lMek0kmvcZZn9nLf) holds the maintained quickstart snippets for both routes.

| Host | Employee setup (cloud MCP, OAuth) |
| --- | --- |
| Codex | Add `ecology` (GA) and, if needed, `ecology-latest` in `~/.codex/config.toml` with their cloud MCP URLs; run `codex mcp login <server>` for each, complete Feishu consent, then restart the session |
| Pi | Add the same `ecology` / `ecology-latest` entries under `mcpServers` in `~/.pi/agent/mcp.json`; run `pi mcp login <server>` for each, complete Feishu consent, then `/reload` |

Employee entries have no local command, custom Authorization header or Key binding; the host stores and refreshes OAuth. Sign in from a browser profile in the configured enterprise; another profile can return `access_denied`. If sign-in fails, report it once to the integration contact; do not bypass enterprise checks or reuse other CLI tokens.

Third parties use GA with their own Key: `codex mcp add ecology-partner --url https://ecology.growatt.com/api/v1/ecology/mcp --bearer-token-env-var ECOLOGY_API_TOKEN` (or the same with `pi`), with the Key in the host's secret launch environment. Latest is for internal acceptance. Never print a full MCP configuration or credential store while checking whether a connection exists.

Installing this Skill does not install a connector, create a Key or grant access.
