#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultCobraDemoHandle } from "./handle.js";
import { createYorishiroCobraDemoMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultCobraDemoHandle({});
  const server = createYorishiroCobraDemoMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-cobra-demo-mcp] stdio; binary=cobra-demo");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-cobra-demo-mcp] fatal:", err);
  process.exit(1);
});
