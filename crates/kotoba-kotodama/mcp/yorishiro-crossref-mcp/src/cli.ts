#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultCrossrefHandle } from "./handle.js";
import { createYorishiroCrossrefMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_CROSSREF_BASE_URL ?? "https://api.crossref.org";
  const handle = createDefaultCrossrefHandle({ baseUrl });
  const server = createYorishiroCrossrefMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-crossref-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-crossref-mcp] fatal:", err);
  process.exit(1);
});
