#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultArgparseDemoHandle } from "./handle.js";
import { createYorishiroArgparseDemoMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultArgparseDemoHandle({});
  const server = createYorishiroArgparseDemoMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-argparse-demo-mcp] stdio; binary=argparse-demo");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-argparse-demo-mcp] fatal:", err);
  process.exit(1);
});
