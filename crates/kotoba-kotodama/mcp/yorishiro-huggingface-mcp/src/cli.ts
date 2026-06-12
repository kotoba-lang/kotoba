#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultHuggingfaceHandle } from "./handle.js";
import { createYorishiroHuggingfaceMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_HUGGINGFACE_BASE_URL ?? "https://huggingface.co";
  const handle = createDefaultHuggingfaceHandle({ baseUrl });
  const server = createYorishiroHuggingfaceMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-huggingface-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-huggingface-mcp] fatal:", err);
  process.exit(1);
});
