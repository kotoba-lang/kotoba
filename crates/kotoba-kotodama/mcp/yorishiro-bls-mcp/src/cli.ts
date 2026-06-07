#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultBlsHandle } from "./handle.js";
import { createYorishiroBlsMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_BLS_BASE_URL ?? "https://api.bls.gov";
  const handle = createDefaultBlsHandle({ baseUrl });
  const server = createYorishiroBlsMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-bls-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-bls-mcp] fatal:", err);
  process.exit(1);
});
