// langserver-xrpc-handler.test.ts — Tests for the AppView XRPC handler.

import { describe, expect, it } from "vitest";

import { createLangserverXrpcHandler } from "../src/langserver-xrpc-handler.js";
import {
  IsicActor,
  LangserverActorError,
  UnispscActor,
  type Taxonomy,
} from "../src/langserver-actor.js";

function buildMockedActor(taxonomy: Taxonomy, calls: Array<{ url: string; init: RequestInit }>) {
  const fetcher = {
    async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : (input as Request).url;
      const i = init ?? {};
      calls.push({ url, init: i });
      // Synthesize lexicon-shaped responses based on the route the actor calls.
      if (url.endsWith(".health") || url.endsWith("/health")) {
        return new Response(
          JSON.stringify({ status: "healthy", registryReady: true, agentCount: 0 }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.endsWith(".classify")) {
        return new Response(
          JSON.stringify({
            candidates: [{ code: "10101501", confidence: 0.9, title: "stub" }],
            modelUsed: "claude-haiku-4-5-20251001",
            escalated: false,
            elapsedMs: 1,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.endsWith(".invokeAgent")) {
        return new Response(
          JSON.stringify({ ok: true, result: { ok: true } }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.includes(".listAgents")) {
        return new Response(
          JSON.stringify({ agents: [], totalCount: 0 }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.endsWith(".hierarchicalClassify")) {
        return new Response(
          JSON.stringify({
            path: { class: { code: "0111", title: "Growing of cereals", confidence: 0.9 } },
            modelUsed: "claude-haiku-4-5-20251001",
            escalated: false,
            elapsedMs: 1,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response("not-found", { status: 404 });
    },
  };
  return taxonomy === "unispsc"
    ? new UnispscActor({ endpoint: "http://lg", fetcher })
    : new IsicActor({ endpoint: "http://lg", fetcher });
}

function jsonRequest(path: string, body?: unknown): Request {
  return new Request(`http://appview.test${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

describe("createLangserverXrpcHandler — UNSPSC", () => {
  it("serves a service banner with the four NSIDs", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });
    const res = await app.fetch(jsonRequest("/"));
    const body = (await res.json()) as { taxonomy: string; lexicons: string[] };
    expect(body.taxonomy).toBe("unispsc");
    expect(body.lexicons).toContain("com.etzhayyim.apps.unispsc.classify");
    expect(body.lexicons).not.toContain("com.etzhayyim.apps.isic.hierarchicalClassify");
  });

  it("classify validates body + delegates to actor", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });

    const ok = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.classify", { description: "cattle", topK: 1 }),
    );
    expect(ok.status).toBe(200);
    const body = (await ok.json()) as { candidates: Array<{ code: string }>; modelUsed: string };
    expect(body.candidates[0].code).toBe("10101501");
    expect(calls[0].url).toBe("http://lg/xrpc/com.etzhayyim.apps.unispsc.classify");

    const bad = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.classify", { description: "" }),
    );
    expect(bad.status).toBe(400);
    expect(await bad.json()).toEqual({ error: "DescriptionEmpty" });
  });

  it("invokeAgent passes code + payload through to actor", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });

    const ok = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.invokeAgent", {
        code: "10101501",
        payload: { animal_id: "cow-001" },
      }),
    );
    expect(ok.status).toBe(200);
    const body = (await ok.json()) as { ok: boolean };
    expect(body.ok).toBe(true);

    const bad = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.invokeAgent", { code: "10101501" }),
    );
    expect(bad.status).toBe(400);
  });

  it("listAgents builds query string from URL params", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });
    const ok = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.listAgents?prefix=10&limit=2"),
    );
    expect(ok.status).toBe(200);
    expect(calls[0].url).toContain("/xrpc/com.etzhayyim.apps.unispsc.listAgents");
    expect(calls[0].url).toContain("prefix=10");
    expect(calls[0].url).toContain("limit=2");
  });

  it("health endpoint surfaces actor health", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });
    const ok = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.health"),
    );
    const body = (await ok.json()) as { status: string };
    expect(body.status).toBe("healthy");
  });

  it("hierarchicalClassify is NOT mounted for unispsc", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("unispsc", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });
    const res = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.hierarchicalClassify", {
        description: "x",
      }),
    );
    expect(res.status).toBe(404);
  });
});

describe("createLangserverXrpcHandler — ISIC", () => {
  it("service banner includes hierarchicalClassify", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("isic", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "isic",
      endpoint: "http://lg",
      actor,
    });
    const res = await app.fetch(jsonRequest("/"));
    const body = (await res.json()) as { lexicons: string[] };
    expect(body.lexicons).toContain("com.etzhayyim.apps.isic.hierarchicalClassify");
  });

  it("invokeAgent uses classCode field for ISIC", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("isic", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "isic",
      endpoint: "http://lg",
      actor,
    });

    // Missing classCode -> 400
    const bad = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.isic.invokeAgent", {
        code: "0111",
        payload: {},
      }),
    );
    expect(bad.status).toBe(400);

    // Valid classCode -> proxied
    const ok = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.isic.invokeAgent", {
        classCode: "0111",
        payload: { crop_id: "wheat-2026" },
      }),
    );
    expect(ok.status).toBe(200);
    expect(calls[0].url).toBe("http://lg/xrpc/com.etzhayyim.apps.isic.invokeAgent");
  });

  it("hierarchicalClassify is mounted for isic", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const actor = buildMockedActor("isic", calls);
    const app = createLangserverXrpcHandler({
      taxonomy: "isic",
      endpoint: "http://lg",
      actor,
    });
    const res = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.isic.hierarchicalClassify", {
        description: "wheat farm",
        stopAt: "class",
      }),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      path: { class?: { code: string } };
    };
    expect(body.path.class?.code).toBe("0111");
  });
});

describe("error propagation", () => {
  it("LangserverActorError keeps its status code", async () => {
    const failingFetcher = {
      async fetch(): Promise<Response> {
        return new Response(JSON.stringify({ detail: "AgentNotFound" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        });
      },
    };
    const actor = new UnispscActor({
      endpoint: "http://lg",
      fetcher: failingFetcher,
    });
    const app = createLangserverXrpcHandler({
      taxonomy: "unispsc",
      endpoint: "http://lg",
      actor,
    });
    const res = await app.fetch(
      jsonRequest("/xrpc/com.etzhayyim.apps.unispsc.invokeAgent", {
        code: "00000000",
        payload: {},
      }),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { error: string };
    expect(body.error).toBe("AgentNotFound");
    expect(actor).toBeInstanceOf(UnispscActor);
    expect(new LangserverActorError("x", 1).status).toBe(1);
  });
});
