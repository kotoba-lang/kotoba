#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultExamplePortalHandle } from "./handle.js";
import { createYorishiroExamplePortalMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultExamplePortalHandle({});
  const server = createYorishiroExamplePortalMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-example-portal-mcp] stdio; base=https://example.com");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-example-portal-mcp] fatal:", err);
  process.exit(1);
});
