// tools.test.ts — Unit tests for the 9 MCP tool handlers.
//
// The tools are mostly thin adapters over the Phase 6 actor wrappers,
// so we mock the actors and verify each handler returns the actor's
// result unchanged and validates input via zod.

import { describe, expect, it } from "vitest";

import {
  classifyUnispscInputSchema,
  invokeUnispscAgentInputSchema,
  listUnispscAgentsInputSchema,
  classifyIsicInputSchema,
  classifyIsicHierarchicalInputSchema,
  invokeIsicAgentInputSchema,
  listIsicAgentsInputSchema,
  findTool,
  tools,
  type ActorsHandle,
} from "../src/tools.js";

function makeMockActors(): {
  actors: ActorsHandle;
  calls: Array<{ taxonomy: "unispsc" | "isic"; method: string; args: unknown }>;
} {
  const calls: Array<{ taxonomy: "unispsc" | "isic"; method: string; args: unknown }> = [];
  const tag = (taxonomy: "unispsc" | "isic", method: string) =>
    (...args: unknown[]) => {
      calls.push({ taxonomy, method, args: args[0] });
      switch (method) {
        case "classify":
          return Promise.resolve({
            candidates: [],
            modelUsed: "stub",
            escalated: false,
            elapsedMs: 0,
          });
        case "invokeAgent":
          return Promise.resolve({ ok: true, result: { taxonomy, method } });
        case "listAgents":
          return Promise.resolve({ agents: [], totalCount: 0 });
        case "health":
          return Promise.resolve({
            status: "healthy",
            registryReady: true,
            agentCount: 0,
          });
        case "hierarchicalClassify":
          return Promise.resolve({
            path: {},
            modelUsed: "stub",
            escalated: false,
            elapsedMs: 0,
          });
        default:
          throw new Error(`unexpected method ${method}`);
      }
    };
  const actors = {
    unispsc: {
      classify: tag("unispsc", "classify"),
      invokeAgent: tag("unispsc", "invokeAgent"),
      listAgents: tag("unispsc", "listAgents"),
      health: tag("unispsc", "health"),
    },
    isic: {
      classify: tag("isic", "classify"),
      invokeAgent: tag("isic", "invokeAgent"),
      listAgents: tag("isic", "listAgents"),
      health: tag("isic", "health"),
      hierarchicalClassify: tag("isic", "hierarchicalClassify"),
    },
  } as unknown as ActorsHandle;
  return { actors, calls };
}

describe("tools.findTool", () => {
  it("returns each of the 9 tools by name", () => {
    const names = tools.map((t) => t.name);
    expect(names.length).toBe(9);
    expect(new Set(names).size).toBe(9);
    for (const name of names) {
      expect(findTool(name)).toBeDefined();
    }
  });

  it("returns undefined for unknown tools", () => {
    expect(findTool("does_not_exist")).toBeUndefined();
  });
});

describe("zod input schemas", () => {
  it("classify_unispsc requires description, defaults topK=5", () => {
    const parsed = classifyUnispscInputSchema.parse({ description: "cattle" });
    expect(parsed.description).toBe("cattle");
    expect(parsed.topK).toBe(5);
  });

  it("classify_unispsc rejects empty description", () => {
    expect(() => classifyUnispscInputSchema.parse({ description: "" })).toThrow();
  });

  it("invoke_unispsc_agent requires code + payload", () => {
    expect(() => invokeUnispscAgentInputSchema.parse({})).toThrow();
    const parsed = invokeUnispscAgentInputSchema.parse({
      code: "10101501",
      payload: { animal_id: "cow-001" },
    });
    expect(parsed.code).toBe("10101501");
  });

  it("list_unispsc_agents defaults limit=100", () => {
    const parsed = listUnispscAgentsInputSchema.parse({});
    expect(parsed.limit).toBe(100);
  });

  it("classify_isic_hierarchical defaults stopAt=class", () => {
    const parsed = classifyIsicHierarchicalInputSchema.parse({
      description: "wheat farm",
    });
    expect(parsed.stopAt).toBe("class");
  });

  it("invoke_isic_agent requires 4-digit classCode", () => {
    expect(() =>
      invokeIsicAgentInputSchema.parse({ classCode: "01", payload: {} }),
    ).toThrow();
    expect(() =>
      invokeIsicAgentInputSchema.parse({ classCode: "0111", payload: {} }),
    ).not.toThrow();
  });

  it("list_isic_agents accepts section + divisionPrefix", () => {
    const parsed = listIsicAgentsInputSchema.parse({
      section: "A",
      divisionPrefix: "01",
    });
    expect(parsed.section).toBe("A");
    expect(parsed.divisionPrefix).toBe("01");
  });

  it("classify_isic uses topK + modelHint", () => {
    const parsed = classifyIsicInputSchema.parse({
      description: "wheat farm",
      topK: 3,
      modelHint: "sonnet-4.6",
    });
    expect(parsed.topK).toBe(3);
    expect(parsed.modelHint).toBe("sonnet-4.6");
  });
});

describe("tool handlers delegate to the right actor method", () => {
  it("classify_unispsc -> unispsc.classify", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("classify_unispsc");
    expect(tool).toBeDefined();
    await tool!.handler({ description: "cattle" } as never, actors);
    expect(calls).toEqual([
      { taxonomy: "unispsc", method: "classify", args: { description: "cattle" } },
    ]);
  });

  it("invoke_unispsc_agent -> unispsc.invokeAgent", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("invoke_unispsc_agent");
    await tool!.handler({ code: "10101501", payload: {} } as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "unispsc", method: "invokeAgent" });
  });

  it("list_unispsc_agents -> unispsc.listAgents", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("list_unispsc_agents");
    await tool!.handler({ prefix: "10", limit: 50 } as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "unispsc", method: "listAgents" });
  });

  it("unispsc_health -> unispsc.health", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("unispsc_health");
    await tool!.handler({} as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "unispsc", method: "health" });
  });

  it("classify_isic -> isic.classify", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("classify_isic");
    await tool!.handler({ description: "wheat" } as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "isic", method: "classify" });
  });

  it("classify_isic_hierarchical -> isic.hierarchicalClassify", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("classify_isic_hierarchical");
    await tool!.handler({ description: "wheat" } as never, actors);
    expect(calls[0]).toMatchObject({
      taxonomy: "isic",
      method: "hierarchicalClassify",
    });
  });

  it("invoke_isic_agent -> isic.invokeAgent", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("invoke_isic_agent");
    await tool!.handler(
      { classCode: "0111", payload: {} } as never,
      actors,
    );
    expect(calls[0]).toMatchObject({ taxonomy: "isic", method: "invokeAgent" });
  });

  it("list_isic_agents -> isic.listAgents", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("list_isic_agents");
    await tool!.handler({ section: "A" } as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "isic", method: "listAgents" });
  });

  it("isic_health -> isic.health", async () => {
    const { actors, calls } = makeMockActors();
    const tool = findTool("isic_health");
    await tool!.handler({} as never, actors);
    expect(calls[0]).toMatchObject({ taxonomy: "isic", method: "health" });
  });
});
