#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultArxivHandle } from "./handle.js";
import { createYorishiroArxivMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_ARXIV_BASE_URL ?? "http://export.arxiv.org/api";
  const handle = createDefaultArxivHandle({ baseUrl });
  const server = createYorishiroArxivMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-arxiv-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-arxiv-mcp] fatal:", err);
  process.exit(1);
});
