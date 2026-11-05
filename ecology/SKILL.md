---
name: ecology
description: Browse Growatt products, select one inverter by market and rated kW or one accessory unit by market and model, or configure systems through the Ecology API or MCP. Default to product information and component quantities; query or verify PN only when explicitly requested. Does not place orders, manage API Keys or maintain the server.
---

# Ecology

This Skill tells you how to connect to the Ecology service. The service supplies the workflow, contract, catalog, rules, quantities and PN candidates. These change with each release. Do not answer from memory or from a copy.

## Terms

| Term | Meaning |
| --- | --- |
| Environment | One Ecology deployment: **GA** or **Latest** (table below). Each has its own grants, quotas and credentials. |
| Route | How you call one environment: **HTTP** API or cloud **MCP** server. |
| Credential | An application Key or an employee OAuth token for one environment. A credential works only in its own environment. |
| Workflow | The deployed rules for task depth, markets, PN, pins, presentation and errors. You read it from the environment you use. |

| Environment | HTTP base URL | MCP server name and URL | Key variable in the host secret environment |
| --- | --- | --- | --- |
| **GA** (default) | `https://ecology.growatt.com/api/v1/ecology` | `ecology`: `https://ecology.growatt.com/api/v1/ecology/mcp` | `ECOLOGY_API_TOKEN` |
| **Latest** | `https://feishu.myshine.online/api/v1/ecology` | `ecology-latest`: `https://feishu.myshine.online/api/v1/ecology/mcp` | `ECOLOGY_LATEST_API_TOKEN` |

## Procedure

1. **Select the environment.** Use GA. Use Latest only if the user explicitly asks for Latest or myshine.
2. **Select the route** for that environment:
   - If its Key variable is set, or the host gives you an employee OAuth token for it, use HTTP.
   - Else, if its MCP server is configured, use MCP.
   - Else, stop. Tell the user that this environment is not set up, and refer to [connection](references/connection.md).
3. **Read the workflow** once per task, from the same environment:

   | Route | Always | Only if the user asks for PN or material codes | Only for NOAH, NEXA or AURA scenes |
   | --- | --- | --- | --- |
   | HTTP | `GET /workflow` | `GET /workflow/materials` | `GET /workflow/plug-in` |
   | MCP | resource `ecology://workflow` | `ecology://workflow/materials` | `ecology://workflow/plug-in` |

   - If HTTP `GET /workflow` returns 404, the environment is older than this endpoint. If the MCP server of the same environment is configured, read the workflow there.
   - If you cannot read the workflow, tell the user. Then give only product and model information. Do not call `materials` or `evaluate`.
4. **Follow the workflow.** Get operations, inputs and limits from the service, not from memory:
   - `GET /portfolio` → `endpoints`: operations, paths, tool names, scopes, required inputs and availability for this credential.
   - A product's `next_actions`: the next operations for that product and market.
   - Response header `X-Ecology-API-Version`: the contract version of this environment.
5. **Report the source.** In each answer, name the environment (GA or Latest) and its contract version.

## Credential rules

- Send `Authorization: Bearer <credential>` with the credential of the selected environment only.
- Do not put a credential in a URL, file, command argument or output.
- Do not use the other environment after a denial or an error. Do not change the credential type after a denial.
- Do not take a token from an MCP connection to use with HTTP. Do not create a Key to change the route.
- On HTTP, send a descriptive `User-Agent`. A 403 with the plain-text body `error code: 1010` comes from the network edge, not from the credential: set a `User-Agent` and retry once. If it fails again, report it.

Example (Australia market overview): `GET /market-models?market=AU` over HTTP, or tool `ecology_market_models({"market":"AU"})` over MCP.
