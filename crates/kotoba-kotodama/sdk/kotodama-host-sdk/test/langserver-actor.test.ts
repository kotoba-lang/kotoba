// langserver-actor.test.ts — Tests for the UNSPSC + ISIC actor wrappers.

import { describe, it, expect } from "vitest";
import {
  createIsicActor,
  createLangserverActor,
  createUnispscActor,
  LangserverActorError,
  type HealthOutput,
  type ListAgentsOutput,
} from "../src/langserver-actor.js";

function mockFetcher(
  handler: (url: string, init: RequestInit) => Response | Promise<Response>,
) {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fetcher = {
    async fetch(
      input: RequestInfo | URL,
      init?: RequestInit,
    ): Promise<Response> {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : (input as Request).url;
      const i = init ?? {};
      calls.push({ url, init: i });
      return handler(url, i);
    },
  };
  return { fetcher, calls };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("UnispscActor", () => {
  it("classify POSTs lexicon NSID with the input body", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        candidates: [
          { code: "10101501", confidence: 0.9, title: "Livestock" },
        ],
        modelUsed: "claude-haiku-4-5-20251001",
        escalated: false,
        elapsedMs: 12,
      }),
    );
    const actor = createUnispscActor({
      endpoint: "http://lg.test",
      fetcher,
    });
    const result = await actor.classify({ description: "live cattle", topK: 3 });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.unispsc.classify",
    );
    expect(calls[0].init.method).toBe("POST");
    expect(JSON.parse(calls[0].init.body as string)).toEqual({
      description: "live cattle",
      topK: 3,
    });
    expect(result.candidates[0].code).toBe("10101501");
    expect(result.escalated).toBe(false);
  });

  it("invokeAgent POSTs code + payload and returns the agent state", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        ok: true,
        result: { animal_id: "cow-001", health_status: "certified" },
        modelUsed: "n/a",
        elapsedMs: 11,
      }),
    );
    const actor = createUnispscActor({
      endpoint: "http://lg.test",
      fetcher,
    });
    const out = await actor.invokeAgent({
      code: "10101501",
      payload: {
        animal_id: "cow-001",
        health_status: "pending",
        quarantine_verified: false,
        transport_logs: [],
      },
    });
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.unispsc.invokeAgent",
    );
    expect(out.ok).toBe(true);
    expect(out.result?.health_status).toBe("certified");
  });

  it("listAgents builds a query string from prefix/limit/cursor", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        agents: [{ code: "10101501", module: "p.unispsc_agents.c10101501", loaded: false }],
        totalCount: 18342,
        cursor: "10101501",
      }),
    );
    const actor = createUnispscActor({ endpoint: "http://lg.test", fetcher });
    const out = await actor.listAgents({ prefix: "101", limit: 1 });
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.unispsc.listAgents?prefix=101&limit=1",
    );
    expect(out.totalCount).toBe(18342);
    expect(out.cursor).toBe("10101501");
  });

  it("health hits the lexicon health endpoint", async () => {
    const body: HealthOutput = {
      status: "healthy",
      registryReady: true,
      agentCount: 18342,
      warmAgents: 1,
      modelsAvailable: ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
      uptimeMs: 123,
      taxonomy: "unispsc",
    };
    const { fetcher, calls } = mockFetcher(() => json(body));
    const actor = createUnispscActor({ endpoint: "http://lg.test", fetcher });
    const out = await actor.health();
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.unispsc.health",
    );
    expect(out.agentCount).toBe(18342);
  });

  it("404 from langserver becomes LangserverActorError with status + detail", async () => {
    const { fetcher } = mockFetcher(() =>
      json({ detail: "AgentNotFound" }, 404),
    );
    const actor = createUnispscActor({ endpoint: "http://lg.test", fetcher });
    await expect(
      actor.invokeAgent({ code: "00000000", payload: {} }),
    ).rejects.toMatchObject({
      name: "LangserverActorError",
      message: "AgentNotFound",
      status: 404,
    });
  });
});

describe("IsicActor", () => {
  it("classify uses the isic NSID and returns classCode candidates", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        candidates: [
          { classCode: "0111", confidence: 0.92, title: "Growing of cereals" },
        ],
        modelUsed: "claude-haiku-4-5-20251001",
        escalated: false,
        elapsedMs: 7,
      }),
    );
    const actor = createIsicActor({ endpoint: "http://lg.test", fetcher });
    const out = await actor.classify({ description: "wheat farm" });
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.isic.classify",
    );
    expect(out.candidates[0].classCode).toBe("0111");
  });

  it("hierarchicalClassify POSTs the dedicated NSID with stopAt", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        path: {
          section: { code: "A", title: "Agriculture", confidence: 0.92 },
          division: { code: "01", title: "Crop and animal production", confidence: 0.92 },
          group: { code: "011", title: "Growing of non-perennial crops", confidence: 0.92 },
          class: { code: "0111", title: "Growing of cereals", confidence: 0.92 },
        },
        modelUsed: "claude-haiku-4-5-20251001",
        escalated: false,
        elapsedMs: 9,
      }),
    );
    const actor = createIsicActor({ endpoint: "http://lg.test", fetcher });
    const out = await actor.hierarchicalClassify({
      description: "wheat farm",
      stopAt: "class",
    });
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.isic.hierarchicalClassify",
    );
    expect(JSON.parse(calls[0].init.body as string).stopAt).toBe("class");
    expect(out.path.class?.code).toBe("0111");
  });

  it("invokeAgent accepts classCode and routes through invokeAgent NSID", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({ ok: true, result: { graded: "B" }, elapsedMs: 4 }),
    );
    const actor = createIsicActor({ endpoint: "http://lg.test", fetcher });
    const out = await actor.invokeAgent({
      classCode: "0111",
      payload: { crop_id: "wheat-2026" },
    });
    expect(calls[0].url).toBe(
      "http://lg.test/xrpc/com.etzhayyim.apps.isic.invokeAgent",
    );
    expect(JSON.parse(calls[0].init.body as string).classCode).toBe("0111");
    expect(out.ok).toBe(true);
  });
});

describe("createLangserverActor", () => {
  it("defaults to in-cluster Service DNS by taxonomy", async () => {
    const { fetcher, calls } = mockFetcher(() =>
      json({
        status: "healthy",
        registryReady: true,
        agentCount: 0,
      } satisfies HealthOutput),
    );
    const unispsc = createLangserverActor("unispsc", { fetcher });
    await unispsc.health();
    expect(calls[0].url).toBe(
      "http://lg-open-unispsc.lg-open-unispsc.svc:80/xrpc/com.etzhayyim.apps.unispsc.health",
    );

    const isic = createLangserverActor("isic", { fetcher });
    await isic.health();
    expect(calls[1].url).toBe(
      "http://lg-open-isic.lg-open-isic.svc:80/xrpc/com.etzhayyim.apps.isic.health",
    );
  });

  it("explicit endpoint overrides the in-cluster default", async () => {
    const { fetcher, calls } = mockFetcher(() => json({ agents: [], totalCount: 0 } satisfies ListAgentsOutput));
    const isic = createLangserverActor("isic", {
      endpoint: "https://isic.etzhayyim.com",
      fetcher,
    });
    await isic.listAgents({});
    expect(calls[0].url).toBe(
      "https://isic.etzhayyim.com/xrpc/com.etzhayyim.apps.isic.listAgents",
    );
  });
});

describe("error semantics", () => {
  it("LangserverActorError preserves status + raw body", async () => {
    const { fetcher } = mockFetcher(() => json({ detail: "DescriptionEmpty" }, 400));
    const actor = createUnispscActor({ endpoint: "http://lg.test", fetcher });
    try {
      await actor.classify({ description: "" });
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(LangserverActorError);
      const err = e as LangserverActorError;
      expect(err.status).toBe(400);
      expect(err.message).toBe("DescriptionEmpty");
    }
  });

  it("non-JSON 5xx still surfaces with HTTP status", async () => {
    const { fetcher } = mockFetcher(
      () =>
        new Response("upstream timeout", {
          status: 502,
          headers: { "content-type": "text/plain" },
        }),
    );
    const actor = createUnispscActor({ endpoint: "http://lg.test", fetcher });
    await expect(actor.health()).rejects.toMatchObject({
      name: "LangserverActorError",
      status: 502,
    });
  });
});
