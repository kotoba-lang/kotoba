#!/usr/bin/env node
// cli.ts — Stdio MCP server entry point.
//
// Reads two env vars:
//   LG_UNISPSC_ENDPOINT  base URL of the UNSPSC langserver (defaults to
//                        http://lg-open-unispsc.lg-open-unispsc.svc:80)
//   LG_ISIC_ENDPOINT     base URL of the ISIC langserver (defaults to
//                        http://lg-open-isic.lg-open-isic.svc:80)
//
// Spawned by an MCP host (Claude Desktop, Codex CLI, Cursor, etc.) over
// stdio. Logs go to stderr; stdout is reserved for the JSON-RPC stream.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  createIsicActor,
  createUnispscActor,
} from "@etzhayyim/kotodama-host-sdk";

import { createUnispscIsicMcpServer } from "./server.js";

async function main(): Promise<void> {
  const unispscEndpoint =
    process.env.LG_UNISPSC_ENDPOINT ??
    "http://lg-open-unispsc.lg-open-unispsc.svc:80";
  const isicEndpoint =
    process.env.LG_ISIC_ENDPOINT ??
    "http://lg-open-isic.lg-open-isic.svc:80";

  const unispsc = createUnispscActor({ endpoint: unispscEndpoint });
  const isic = createIsicActor({ endpoint: isicEndpoint });

  const server = createUnispscIsicMcpServer({ actors: { unispsc, isic } });
  const transport = new StdioServerTransport();

  console.error(
    `[unispsc-isic-mcp] starting stdio server; ` +
      `UNISPSC=${unispscEndpoint} ISIC=${isicEndpoint}`,
  );
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[unispsc-isic-mcp] fatal:", err);
  process.exit(1);
});
