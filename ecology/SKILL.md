---
name: ecology
description: Browse Growatt products, select one inverter by market and rated kW or one accessory unit by market and model, or configure systems through the Ecology API or MCP. Default to product information and component quantities; query or verify PN only when explicitly requested. Does not place orders, manage API Keys or maintain the server.
---

# Ecology

This Skill only connects you to the Ecology service; the service supplies everything else. Its workflow, contract, catalog, rules, quantities and candidates change with each release, so never answer from memory or from a copy.

## Connect

- **HTTP API** (default): `https://ecology.growatt.com/api/v1/ecology`.
- **Cloud MCP** (Streamable HTTP): `https://ecology.growatt.com/api/v1/ecology/mcp`. Use it when it is the chosen connection or no API credential is configured.
- Send `Authorization: Bearer` with an application Key from the host's secret environment or a host-managed employee OAuth token. Never put a credential in a URL, file, command argument or output.
- Keep the connection and identity already chosen for the task. Do not extract an MCP token for HTTP, create a Key to change route, or switch identity after a denial.
- Host setup and the Key-versus-OAuth choice: [connection](references/connection.md).
- Send a descriptive `User-Agent` on HTTP. A plain-text 403 `error code: 1010` is an edge block of the client signature, not a credential problem: set a `User-Agent` and retry once.

## Then read the workflow from the service

Read the deployed workflow once per task and follow it; it covers task depth, markets, PN rules, pins, presentation and errors.

| Route | Core workflow | Only for PN work | Only for NOAH/NEXA/AURA |
| --- | --- | --- | --- |
| HTTP | `GET /workflow` | `GET /workflow/materials` | `GET /workflow/plug-in` |
| MCP | `ecology://workflow` | `ecology://workflow/materials` | `ecology://workflow/plug-in` |

If HTTP `/workflow` returns 404, the service predates it: read the MCP resource instead, or report that the workflow is unavailable. Never substitute a repository copy. Operations, inputs and the contract version also come from the service: `GET /portfolio` `endpoints`, a product's `next_actions`, and the `X-Ecology-API-Version` header.

Example, one Australian market overview: `ecology_market_models({"market":"AU"})` over MCP, or `GET /market-models?market=AU` over HTTP.
