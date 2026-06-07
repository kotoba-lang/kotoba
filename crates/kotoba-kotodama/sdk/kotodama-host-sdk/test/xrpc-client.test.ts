// xrpc-client.test.ts — Tests for XrpcClient class.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { XrpcClient } from "../src/xrpc-client.js";

function createMockFetcher(responseBody: unknown = { ok: true }, status = 200) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  return {
    calls,
    fetcher: {
      async fetch(input: string | Request, init?: RequestInit): Promise<Response> {
        const url = typeof input === "string" ? input : input.url;
        calls.push({ url, init });
        return new Response(JSON.stringify(responseBody), {
          status,
          headers: { "content-type": "application/json" },
        });
      },
    },
  };
}

describe("XrpcClient", () => {
  let client: XrpcClient;
  let calls: Array<{ url: string; init?: RequestInit }>;

  beforeEach(() => {
    const mock = createMockFetcher({ uri: "at://did:web:test/col/rkey1", cid: "cid1", rkey: "rkey1" });
    calls = mock.calls;
    client = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test.etzhayyim.com" });
  });

  // ── Generic CRUD ──

  it("createRecord sends POST to com.atproto.repo.createRecord", async () => {
    await client.createRecord("com.etzhayyim.apps.test.article", { title: "Hello" });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/xrpc/com.atproto.repo.createRecord");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.repo).toBe("did:web:test.etzhayyim.com");
    expect(body.collection).toBe("com.etzhayyim.apps.test.article");
    expect(body.record).toEqual({ title: "Hello" });
  });

  it("createRecord includes rkey when provided", async () => {
    await client.createRecord("col", { data: 1 }, "custom-rkey");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.rkey).toBe("custom-rkey");
  });

  it("getRecord sends POST to com.atproto.repo.getRecord", async () => {
    await client.getRecord("com.etzhayyim.apps.test.article", "rkey1");
    expect(calls[0].url).toContain("/xrpc/com.atproto.repo.getRecord");
  });

  it("getRecord returns null on fetch error", async () => {
    const failMock = createMockFetcher({}, 404);
    // Need a client that actually throws on !resp.ok for getRecord
    // Actually getRecord catches errors and returns null
    const failClient = new XrpcClient({
      pdsRpc: {
        async fetch() { throw new Error("network error"); },
      } as any,
      repo: "did:web:test",
    });
    const result = await failClient.getRecord("col", "rkey");
    expect(result).toBeNull();
  });

  it("listRecords sends POST to com.atproto.repo.listRecords", async () => {
    const mock = createMockFetcher({ records: [], cursor: undefined });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    await c.listRecords("com.etzhayyim.apps.test.article", { limit: 25 });
    const body = JSON.parse(mock.calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.test.article");
    expect(body.limit).toBe(25);
  });

  it("listRecords defaults to limit 50", async () => {
    const mock = createMockFetcher({ records: [] });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    await c.listRecords("col");
    const body = JSON.parse(mock.calls[0].init?.body as string);
    expect(body.limit).toBe(50);
  });

  it("deleteRecord sends POST to com.atproto.repo.deleteRecord", async () => {
    await client.deleteRecord("com.etzhayyim.apps.test.article", "rkey1");
    expect(calls[0].url).toContain("/xrpc/com.atproto.repo.deleteRecord");
  });

  it("putRecord sends POST to com.atproto.repo.putRecord", async () => {
    await client.putRecord("com.etzhayyim.apps.test.article", "rkey1", { title: "Updated" });
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.rkey).toBe("rkey1");
    expect(body.record).toEqual({ title: "Updated" });
  });

  // ── Domain shorthand ──

  it("domain().create builds correct collection", async () => {
    await client.domain("handotai").create("article", { title: "Test" });
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.handotai.article");
  });

  it("domain().get builds correct collection", async () => {
    await client.domain("handotai").get("article", "r1");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.handotai.article");
    expect(body.rkey).toBe("r1");
  });

  it("domain().list builds correct collection", async () => {
    const mock = createMockFetcher({ records: [] });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    await c.domain("handotai").list("article");
    const body = JSON.parse(mock.calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.handotai.article");
  });

  it("domain().delete builds correct collection", async () => {
    await client.domain("handotai").delete("article", "r1");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.handotai.article");
  });

  it("domain().put builds correct collection", async () => {
    await client.domain("handotai").put("article", "r1", { title: "Updated" });
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("com.etzhayyim.apps.handotai.article");
  });

  it("domain().call sends XRPC to com.etzhayyim.apps.{app}.{method}", async () => {
    await client.domain("handotai").call("generateArticle", { topic: "AI" });
    expect(calls[0].url).toContain("/xrpc/com.etzhayyim.apps.handotai.generateArticle");
  });

  // ── Social shortcuts ──

  it("post creates app.bsky.feed.post record", async () => {
    await client.post("Hello world");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("app.bsky.feed.post");
    expect(body.record.$type).toBe("app.bsky.feed.post");
    expect(body.record.text).toBe("Hello world");
    expect(body.record.createdAt).toBeTruthy();
  });

  it("like creates app.bsky.feed.like record", async () => {
    await client.like("at://did:web:x/app.bsky.feed.post/abc", "cid-abc");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("app.bsky.feed.like");
    expect(body.record.subject.uri).toBe("at://did:web:x/app.bsky.feed.post/abc");
    expect(body.record.subject.cid).toBe("cid-abc");
  });

  it("follow creates app.bsky.graph.follow record", async () => {
    await client.follow("did:web:target");
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.collection).toBe("app.bsky.graph.follow");
    expect(body.record.subject).toBe("did:web:target");
  });

  // ── Profile / Feed reads ──

  it("getProfile calls app.bsky.actor.getProfile", async () => {
    await client.getProfile("did:web:test");
    expect(calls[0].url).toContain("/xrpc/app.bsky.actor.getProfile");
  });

  it("getTimeline calls app.bsky.feed.getTimeline", async () => {
    const mock = createMockFetcher({ feed: [] });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    await c.getTimeline({ limit: 20 });
    const body = JSON.parse(mock.calls[0].init?.body as string);
    expect(body.limit).toBe(20);
  });

  it("getAuthorFeed calls app.bsky.feed.getAuthorFeed", async () => {
    const mock = createMockFetcher({ feed: [] });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    await c.getAuthorFeed("did:web:author");
    expect(mock.calls[0].url).toContain("/xrpc/app.bsky.feed.getAuthorFeed");
  });

  // ── Error handling ──

  it("xrpc throws on non-ok response", async () => {
    const failMock = createMockFetcher({ error: "bad request" }, 400);
    const c = new XrpcClient({ pdsRpc: failMock.fetcher, repo: "did:web:test" });
    await expect(c.xrpc("com.atproto.repo.getRecord", {})).rejects.toMatchObject({ error: "bad request", status: 400 });
  });

  it("xrpc does not set x-kotodama-verified for HTTP path (default)", async () => {
    await client.xrpc("test.method", {});
    const headers = calls[0].init?.headers as Record<string, string>;
    // HTTP path: no x-kotodama-verified
    expect(headers["x-kotodama-verified"]).toBeUndefined();
  });

  it("xrpc with legacy internalToken uses trusted internal headers instead of Authorization", async () => {
    const mock = createMockFetcher({ ok: true });
    const c = new XrpcClient({
      pdsRpc: mock.fetcher,
      repo: "did:web:test",
      internalToken: "legacy-token",
      isServiceBinding: false,
    });
    await c.xrpc("com.atproto.repo.createRecord", { repo: "did:web:test", collection: "app.bsky.feed.post", record: { text: "x" } });
    const headers = mock.calls[0].init?.headers as Record<string, string>;
    expect(headers["authorization"]).toBeUndefined();
    expect(headers["x-kotodama-verified"]).toBe("true");
    expect(headers["x-kotodama-internal-token"]).toBe("legacy-token");
    expect(headers["x-etzhayyim-org-id"]).toBe("service");
  });

  it("xrpc throws TimeoutError on request timeout", async () => {
    const c = new XrpcClient({
      pdsRpc: {
        async fetch(_input: string | Request, init?: RequestInit) {
          return new Promise<Response>((_resolve, reject) => {
            if (init?.signal?.aborted) {
              reject(new DOMException("Aborted", "AbortError"));
              return;
            }
            init?.signal?.addEventListener("abort", () => {
              reject(new DOMException("Aborted", "AbortError"));
            }, { once: true });
          });
        },
      } as any,
      repo: "did:web:test",
      timeoutMs: 1,
    });
    await expect(c.xrpc("com.atproto.repo.getRecord", {})).rejects.toMatchObject({ error: "TimeoutError", status: 408 });
  });

  it("skips legacy internal registration nsids even from dispatch entries", async () => {
    const mock = createMockFetcher({ ok: true });
    const c = new XrpcClient({ pdsRpc: mock.fetcher, repo: "did:web:test" });
    c.dispatch({ type: "identity-register", payload: { nanoid: "n1" } });
    c.dispatch({ type: "capability-declare", payload: { id: "cap-1" } });
    c.dispatch({ type: "agent-register-tools", payload: [{ id: "tool-1" }] });
    await c.drainPendingWrites();
    const urls = mock.calls.map((call) => call.url);
    expect(urls.some((u) => u.includes("/xrpc/com.etzhayyim.identity.register"))).toBe(false);
    expect(urls.some((u) => u.includes("/xrpc/com.etzhayyim.capability.declare"))).toBe(false);
    expect(urls.some((u) => u.includes("/xrpc/com.etzhayyim.agent.registerTools"))).toBe(false);
  });
});
