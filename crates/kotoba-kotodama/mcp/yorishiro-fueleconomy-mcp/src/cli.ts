#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultFueleconomyHandle } from "./handle.js";
import { createYorishiroFueleconomyMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_FUELECONOMY_BASE_URL ?? "https://www.fueleconomy.gov";
  const handle = createDefaultFueleconomyHandle({ baseUrl });
  const server = createYorishiroFueleconomyMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-fueleconomy-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-fueleconomy-mcp] fatal:", err);
  process.exit(1);
});
