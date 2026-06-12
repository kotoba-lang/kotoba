#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultClapDeriveDemoHandle } from "./handle.js";
import { createYorishiroClapDeriveDemoMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultClapDeriveDemoHandle({});
  const server = createYorishiroClapDeriveDemoMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-clap-derive-demo-mcp] stdio; binary=clap-derive-demo");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-clap-derive-demo-mcp] fatal:", err);
  process.exit(1);
});
