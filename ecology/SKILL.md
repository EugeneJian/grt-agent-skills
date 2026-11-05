---
name: ecology
description: Browse Growatt products, select one inverter by market and rated kW or one accessory unit by market and model, or configure systems through the Ecology API or MCP. Default to product information and component quantities; query or verify PN only when explicitly requested. Does not place orders, manage API Keys or maintain the server.
---

# Ecology

This Skill only connects you to the Ecology service; the service supplies everything else. Its workflow, contract, catalog, rules, quantities and candidates change with each release, so never answer from memory or from a copy.

## Connect

Two environments with separate grants and credentials. A credential from one is rejected (401) by the other.

| Environment | Use | HTTP API | Cloud MCP (Streamable HTTP) | Key in host secret environment |
| --- | --- | --- | --- | --- |
| **GA** (default) | Company release | `https://ecology.growatt.com/api/v1/ecology` | `…/api/v1/ecology/mcp`, server `ecology` | `ECOLOGY_API_TOKEN` |
| **Latest** | Newest release under acceptance; use only when asked for latest/myshine or testing a new feature | `https://feishu.myshine.online/api/v1/ecology` | `…/api/v1/ecology/mcp`, server `ecology-latest` | `ECOLOGY_LATEST_API_TOKEN` |

- Prefer HTTP when the chosen environment's Key or host-managed employee OAuth token is available; otherwise use that environment's MCP server.
- Send `Authorization: Bearer` with that environment's credential only. Never put a credential in a URL, file, command argument or output.
- Keep the environment, route and identity chosen for the task, and state which environment answered. Never fall back to the other environment, extract an MCP token for HTTP, create a Key to change route, or switch identity after a denial.
- The two environments can run different contract versions; read `X-Ecology-API-Version` from the one you use.
- Host setup and the Key-versus-OAuth choice: [connection](references/connection.md).
- Send a descriptive `User-Agent` on HTTP. A plain-text 403 `error code: 1010` is an edge block of the client signature, not a credential problem: set a `User-Agent` and retry once.

## Then read the workflow from the service

Read the deployed workflow once per task and follow it; it covers task depth, markets, PN rules, pins, presentation and errors.

| Route | Core workflow | Only for PN work | Only for NOAH/NEXA/AURA |
| --- | --- | --- | --- |
| HTTP | `GET /workflow` | `GET /workflow/materials` | `GET /workflow/plug-in` |
| MCP | `ecology://workflow` | `ecology://workflow/materials` | `ecology://workflow/plug-in` |

If HTTP `/workflow` returns 404, the service predates it: read the MCP resource instead. If neither is available, say so, then answer only read-only product and model information; do not query PNs or evaluate configurations until the workflow is available. Never substitute a repository copy or rules from memory. Operations, inputs and the contract version also come from the service: `GET /portfolio` `endpoints`, a product's `next_actions`, and the `X-Ecology-API-Version` header.

Example, one Australian market overview: `ecology_market_models({"market":"AU"})` over MCP, or `GET /market-models?market=AU` over HTTP.
