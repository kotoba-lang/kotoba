#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultOpenalexHandle } from "./handle.js";
import { createYorishiroOpenalexMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_OPENALEX_BASE_URL ?? "https://api.openalex.org";
  const handle = createDefaultOpenalexHandle({ baseUrl });
  const server = createYorishiroOpenalexMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-openalex-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-openalex-mcp] fatal:", err);
  process.exit(1);
});
