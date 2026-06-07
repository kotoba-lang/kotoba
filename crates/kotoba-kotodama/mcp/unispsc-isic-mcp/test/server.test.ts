// server.test.ts — MCP server / ListTools + CallTool dispatch tests.

import { describe, expect, it } from "vitest";

import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { createUnispscIsicMcpServer, zodToJsonSchema } from "../src/server.js";
import type { ActorsHandle } from "../src/tools.js";
import { z } from "zod";

function makeActors(): ActorsHandle {
  const stub = (kind: string) => ({
    classify: async () => ({ candidates: [], modelUsed: kind, escalated: false, elapsedMs: 1 }),
    invokeAgent: async () => ({ ok: true, result: { kind }, elapsedMs: 1 }),
    listAgents: async () => ({ agents: [], totalCount: 0 }),
    health: async () => ({ status: "healthy", registryReady: true, agentCount: 0 }),
    hierarchicalClassify: async () => ({ path: {}, modelUsed: kind, escalated: false, elapsedMs: 1 }),
  });
  return {
    unispsc: stub("unispsc") as unknown as ActorsHandle["unispsc"],
    isic: stub("isic") as unknown as ActorsHandle["isic"],
  };
}

async function dispatch<T>(
  server: ReturnType<typeof createUnispscIsicMcpServer>,
  schema: typeof ListToolsRequestSchema | typeof CallToolRequestSchema,
  payload: unknown,
): Promise<T> {
  // The SDK Server exposes handlers via a private map; the supported way to
  // exercise them in tests is via the transport. We bypass the transport by
  // calling the registered handler directly. Cast through unknown.
  const handlers = (server as unknown as {
    _requestHandlers: Map<
      string,
      (req: unknown, extra: unknown) => Promise<unknown>
    >;
  })._requestHandlers;
  const method = schema.shape.method.value;
  const handler = handlers.get(method);
  if (!handler) throw new Error(`no handler for ${method}`);
  return (await handler(payload, {})) as T;
}

describe("createUnispscIsicMcpServer — tools/list", () => {
  it("returns 9 tools with name + description + inputSchema", async () => {
    const server = createUnispscIsicMcpServer({ actors: makeActors() });
    const res = await dispatch<{ tools: Array<{ name: string; inputSchema: unknown }> }>(
      server,
      ListToolsRequestSchema,
      { method: "tools/list", params: {} },
    );
    expect(res.tools.length).toBe(9);
    const names = res.tools.map((t) => t.name).sort();
    expect(names).toEqual(
      [
        "classify_isic",
        "classify_isic_hierarchical",
        "classify_unispsc",
        "invoke_isic_agent",
        "invoke_unispsc_agent",
        "isic_health",
        "list_isic_agents",
        "list_unispsc_agents",
        "unispsc_health",
      ].sort(),
    );
    for (const t of res.tools) {
      expect(t.inputSchema).toBeDefined();
    }
  });
});

describe("createUnispscIsicMcpServer — tools/call dispatch", () => {
  it("classify_unispsc returns structuredContent + text content", async () => {
    const server = createUnispscIsicMcpServer({ actors: makeActors() });
    const res = await dispatch<{
      content: Array<{ type: string; text?: string }>;
      structuredContent?: Record<string, unknown>;
      isError?: boolean;
    }>(server, CallToolRequestSchema, {
      method: "tools/call",
      params: {
        name: "classify_unispsc",
        arguments: { description: "cattle" },
      },
    });
    expect(res.isError).toBeFalsy();
    expect(res.structuredContent).toBeDefined();
    expect(res.structuredContent?.modelUsed).toBe("unispsc");
    expect(res.content[0].type).toBe("text");
    expect(typeof res.content[0].text).toBe("string");
  });

  it("unknown tool name -> isError", async () => {
    const server = createUnispscIsicMcpServer({ actors: makeActors() });
    const res = await dispatch<{
      content: Array<{ type: string; text?: string }>;
      isError?: boolean;
    }>(server, CallToolRequestSchema, {
      method: "tools/call",
      params: { name: "does_not_exist", arguments: {} },
    });
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain("Unknown tool");
  });

  it("invalid args -> InvalidInput error", async () => {
    const server = createUnispscIsicMcpServer({ actors: makeActors() });
    const res = await dispatch<{
      content: Array<{ type: string; text?: string }>;
      isError?: boolean;
    }>(server, CallToolRequestSchema, {
      method: "tools/call",
      params: {
        name: "classify_unispsc",
        arguments: { description: "" }, // empty triggers schema min(1) failure
      },
    });
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain("InvalidInput");
  });
});

describe("zodToJsonSchema", () => {
  it("emits an object schema with required + properties", () => {
    const schema = z.object({
      description: z.string().min(1),
      topK: z.number().int().min(1).max(20).default(5),
    });
    const json = zodToJsonSchema(schema);
    expect(json.type).toBe("object");
    expect((json.properties as Record<string, unknown>).description).toBeDefined();
    const topK = (json.properties as Record<string, { type: string; default?: number }>)
      .topK;
    expect(topK.type).toBe("integer");
    expect(topK.default).toBe(5);
    // Zod 4 native converter marks defaulted fields as required (Draft 2020-12
    // requires explicit absence to fall back to the default).
    const required = (json.required as string[]).sort();
    expect(required).toEqual(["description", "topK"]);
  });

  it("handles enums + optionals", () => {
    const schema = z.object({
      mode: z.enum(["a", "b", "c"]),
      label: z.string().optional(),
    });
    const json = zodToJsonSchema(schema);
    const props = json.properties as Record<
      string,
      { type?: string; enum?: string[]; anyOf?: unknown[] }
    >;
    expect(props.mode.enum).toEqual(["a", "b", "c"]);
    // Optionals serialize as type=string but stay out of `required`.
    expect(json.required).toEqual(["mode"]);
  });
});
