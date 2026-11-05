# Connection

Read this file only to set up a host or to choose between an application Key and employee OAuth. Terms (environment, route, credential, workflow) have the meanings defined in [the Skill](../SKILL.md#terms). The workflow, operations, inputs and contract version come from the service.

## Ownership

| Owner | Role |
| --- | --- |
| `EugeneJian/grt-agent-skills`, `ecology/` | This entry: connection and routing only. It contains no product rules. |
| The Ecology service (each environment) | The only runtime source: workflow, contract, catalog, rules, quantities, PN candidates and verification. |
| `EugeneJian/AI-Copilot` | Maintains the service and the workflow. Do not read it during a task. |

## Environments

| Environment | Who uses it | Credential |
| --- | --- | --- |
| GA (default) | Employees and third parties | GA application Key in `ECOLOGY_API_TOKEN`, or employee OAuth on the GA MCP server `ecology` |
| Latest | Internal acceptance only | Latest application Key in `ECOLOGY_LATEST_API_TOKEN`, or employee OAuth on the Latest MCP server `ecology-latest` |

- Each environment has its own Platform, grants, quotas and OAuth resource. Keys and tokens are issued and revoked separately for each environment.
- Keep the two credentials in separate secret variables and separate MCP entries.
- Both environments have the same operations. Their contract versions and data can differ until Latest is promoted to GA.
- The credential type (Key or OAuth) does not change the configuration rules.
- A host that has only an MCP connection has no HTTP access. Do not take its tokens for HTTP.

## Host setup

The [Feishu guide](https://q02gj5lyidv.feishu.cn/wiki/UxglwhNPzi6lMek0kmvcZZn9nLf) has the maintained quickstart snippets.

**Employee, MCP with OAuth.** Add one MCP entry for each environment you use (URLs in [the Skill](../SKILL.md#terms)):

| Host | Steps |
| --- | --- |
| Codex | Add `ecology`, and `ecology-latest` for Latest, to `~/.codex/config.toml`. Run `codex mcp login <server>` for each. Give consent in Feishu. Restart the session. |
| Pi | Add `ecology`, and `ecology-latest` for Latest, under `mcpServers` in `~/.pi/agent/mcp.json`. Run `pi mcp login <server>` for each. Give consent in Feishu. Run `/reload`. |

- An employee MCP entry has no local command, no Authorization header and no Key variable. The host stores and refreshes the OAuth token.
- Sign in from a browser profile that belongs to the configured enterprise. A different profile can return `access_denied`.
- If sign-in fails, report it once to the integration contact. Do not bypass the enterprise check. Do not reuse tokens from other CLIs.

**Employee or service, HTTP with a Key.** Put the Key in the host secret environment under the variable of its environment: `ECOLOGY_API_TOKEN` for GA, `ECOLOGY_LATEST_API_TOKEN` for Latest.

**Third party.** Use GA with the third party's own Key: `codex mcp add ecology-partner --url https://ecology.growatt.com/api/v1/ecology/mcp --bearer-token-env-var ECOLOGY_API_TOKEN` (same command with `pi`). Put the Key in the host secret environment.

Do not print a full MCP configuration or credential store to check whether a connection exists. Installing this Skill does not install a connector, create a Key or grant access.
