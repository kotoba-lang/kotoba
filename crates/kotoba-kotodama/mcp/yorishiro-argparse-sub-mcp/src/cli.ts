#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultArgparseSubHandle } from "./handle.js";
import { createYorishiroArgparseSubMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultArgparseSubHandle({});
  const server = createYorishiroArgparseSubMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-argparse-sub-mcp] stdio; binary=argparse-sub");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-argparse-sub-mcp] fatal:", err);
  process.exit(1);
});
