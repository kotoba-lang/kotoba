#!/usr/bin/env node
// Stdio MCP server entry point. Spawned by an MCP host over stdio.
// stdout is reserved for the JSON-RPC stream; logs go to stderr.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createDefaultHuggingfaceInferenceHandle } from "./handle.js";
import { createYorishiroHuggingfaceInferenceMcpServer } from "./server.js";

async function main(): Promise<void> {
  const baseUrl = process.env.YORISHIRO_HUGGINGFACE-INFERENCE_BASE_URL ?? "https://api-inference.huggingface.co";
  const handle = createDefaultHuggingfaceInferenceHandle({ baseUrl });
  const server = createYorishiroHuggingfaceInferenceMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error(`[yorishiro-huggingface-inference-mcp] stdio; baseUrl=${baseUrl}`);
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-huggingface-inference-mcp] fatal:", err);
  process.exit(1);
});
