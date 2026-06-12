#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultClapDemoHandle } from "./handle.js";
import { createYorishiroClapDemoMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultClapDemoHandle({});
  const server = createYorishiroClapDemoMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-clap-demo-mcp] stdio; binary=clap-demo");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-clap-demo-mcp] fatal:", err);
  process.exit(1);
});
