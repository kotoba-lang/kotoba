#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultArgparseMultiHandle } from "./handle.js";
import { createYorishiroArgparseMultiMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultArgparseMultiHandle({});
  const server = createYorishiroArgparseMultiMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-argparse-multi-mcp] stdio; binary=argparse-multi");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-argparse-multi-mcp] fatal:", err);
  process.exit(1);
});
