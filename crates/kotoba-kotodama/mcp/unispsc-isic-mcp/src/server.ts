// server.ts — MCP server factory.
//
// Wires the 9 UNSPSC + ISIC tools (see tools.ts) onto an
// `@modelcontextprotocol/sdk` server instance. The same server runs over
// stdio (CLI desktop hosts) and Streamable HTTP (in-cluster service mesh).
//
// Two-step bind so callers can choose the transport:
//
//   const server = createUnispscIsicMcpServer({ actors });
//   await server.connect(new StdioServerTransport());   // CLI
//   // or:
//   const transport = new StreamableHTTPServerTransport({ ... });
//   await server.connect(transport);

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import { type ActorsHandle, findTool, tools } from "./tools.js";

export interface McpServerConfig {
  actors: ActorsHandle;
  name?: string;
  version?: string;
}

export function createUnispscIsicMcpServer(config: McpServerConfig): Server {
  const server = new Server(
    {
      name: config.name ?? "etzhayyim-unispsc-isic",
      version: config.version ?? "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: tools.map((t) => ({
      name: t.name,
      title: t.title,
      description: t.description,
      inputSchema: zodToJsonSchema(t.inputSchema),
    })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const name = req.params.name;
    const tool = findTool(name);
    if (!tool) {
      return {
        isError: true,
        content: [
          {
            type: "text",
            text: `Unknown tool: ${name}`,
          },
        ],
      };
    }

    const parsed = tool.inputSchema.safeParse(req.params.arguments ?? {});
    if (!parsed.success) {
      return {
        isError: true,
        content: [
          {
            type: "text",
            text: `InvalidInput: ${parsed.error.toString()}`,
          },
        ],
      };
    }

    try {
      const result = await tool.handler(parsed.data, config.actors);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
        structuredContent: result as Record<string, unknown>,
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      return {
        isError: true,
        content: [
          {
            type: "text",
            text: errMsg,
          },
        ],
      };
    }
  });

  return server;
}

// Convert a zod schema to JSON Schema (Draft 2020-12) for the MCP
// `tools/list` response. Zod 4 ships a native converter; we delegate.
export function zodToJsonSchema(schema: z.ZodTypeAny): Record<string, unknown> {
  return z.toJSONSchema(schema) as Record<string, unknown>;
}
