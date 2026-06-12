#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultDemoFixtureHandle } from "./handle.js";
import { createYorishiroDemoFixtureMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultDemoFixtureHandle({});
  const server = createYorishiroDemoFixtureMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-demo-fixture-mcp] stdio; binary=demo-fixture");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-demo-fixture-mcp] fatal:", err);
  process.exit(1);
});
