#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createDefaultPdftotextHandle } from "./handle.js";
import { createYorishiroPdftotextMcpServer } from "./server.js";

async function main(): Promise<void> {
  const handle = createDefaultPdftotextHandle({});
  const server = createYorishiroPdftotextMcpServer({ handle });
  const transport = new StdioServerTransport();
  console.error("[yorishiro-pdftotext-mcp] stdio; binary=pdftotext");
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[yorishiro-pdftotext-mcp] fatal:", err);
  process.exit(1);
});
