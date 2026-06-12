import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { findTool, tools, type ArxivHandle } from "./tools.js";

export interface McpServerConfig {
  handle: ArxivHandle;
  name?: string;
  version?: string;
}

export function createYorishiroArxivMcpServer(config: McpServerConfig): Server {
  const server = new Server(
    {
      name: config.name ?? "etzhayyim-yorishiro-arxiv",
      version: config.version ?? "0.1.0",
    },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: tools.map((t) => ({
      name: t.name,
      title: t.title,
      description: t.description,
      inputSchema: t.jsonSchema,
    })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const name = req.params.name;
    const tool = findTool(name);
    if (!tool) {
      return { isError: true, content: [{ type: "text", text: `Unknown tool: ${name}` }] };
    }
    const parsed = tool.inputSchema.safeParse(req.params.arguments ?? {});
    if (!parsed.success) {
      return {
        isError: true,
        content: [{ type: "text", text: `InvalidInput: ${parsed.error.toString()}` }],
      };
    }
    try {
      const out = await tool.invoke(config.handle, parsed.data);
      return { content: [{ type: "text", text: JSON.stringify(out) }] };
    } catch (err) {
      return {
        isError: true,
        content: [{ type: "text", text: `InvokeError: ${(err as Error).message}` }],
      };
    }
  });

  return server;
}
