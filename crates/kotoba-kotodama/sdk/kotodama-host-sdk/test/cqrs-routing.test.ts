// cqrs-routing.test.ts — Tests for CQRS routing and XRPC handling.

import { describe, it, expect, vi } from "vitest";
import { createHostSDK } from "../src/index.js";
import { App, asAgentTool, withCapabilityTags, responsible } from "../src/app.js";
import type { AppContext, HostImports } from "../src/types.js";
import { AssigneeKind } from "../src/types.js";
import { createMockAppDef, createMockHostImports, createMockPdsRpc } from "./mock-helpers.js";

// ── App XRPC Handler Tests ──────────────────────────────────────────────

describe("App HTTP handling", () => {
  function makeApp(host?: Partial<HostImports>) {
    const mockHost = createMockHostImports(host);
    const app = new App(createMockAppDef(), mockHost);
    return app;
  }

  it("responds to /health with 200", async () => {
    const sdk = createHostSDK({ appDef: createMockAppDef(), env: {} });
    const response = await sdk.handleRequest({
      method: "GET",
      url: "https://test.etzhayyim.com/health",
      headers: [],
      body: new Uint8Array(),
    });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("ok");
  });

  it("responds to /healthz with 200", async () => {
    const sdk = createHostSDK({ appDef: createMockAppDef(), env: {} });
    const response = await sdk.handleRequest({
      method: "GET",
      url: "https://test.etzhayyim.com/healthz",
      headers: [],
      body: new Uint8Array(),
    });
    expect(response.status).toBe(200);
  });

  it("returns 404 for unknown routes", async () => {
    const sdk = createHostSDK({ appDef: createMockAppDef(), env: {} });
    const response = await sdk.handleRequest({
      method: "GET",
      url: "https://test.etzhayyim.com/nonexistent",
      headers: [],
      body: new Uint8Array(),
    });
    expect(response.status).toBe(404);
    const body = await response.json();
    expect(body.error).toBe("not found");
  });

  it("POST to registered command name routes correctly", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx: AppContext, payload: Uint8Array) => {
      return new TextEncoder().encode('{"ok":true}');
    });
    app.command("translate", handler);
    const res = await app.handleCommand("translate", [], new TextEncoder().encode("{}"));
    expect(res.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("registered query is accessible via POST", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx: AppContext, _payload: Uint8Array) => {
      return new TextEncoder().encode('{"data":"result"}');
    });
    app.query("search", handler);
    const res = await app.handleCommand("search", [], new Uint8Array());
    expect(res.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });
});

describe("XRPC routing", () => {
  function makeApp() {
    const mockHost = createMockHostImports();
    const app = new App(createMockAppDef({ id: "news" }), mockHost);
    return app;
  }

  it("routes full NSID to command handler", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx: AppContext, _payload: Uint8Array) => {
      return new TextEncoder().encode('{"generated":true}');
    });
    app.command("com.etzhayyim.apps.news.generateArticle", handler);
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.news.generateArticle", [], new Uint8Array());
    expect(res.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("XRPC unknown method returns 404", async () => {
    const app = makeApp();
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.news.nonexistent", [], new Uint8Array());
    expect(res.status).toBe(404);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.error).toContain("unknown xrpc method");
  });

  it("XRPC handler error returns 500", async () => {
    const app = makeApp();
    app.command("com.etzhayyim.apps.news.failing", () => { throw new Error("handler boom"); });
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.news.failing", [], new Uint8Array());
    expect(res.status).toBe(500);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.error).toContain("handler boom");
  });

  it("XRPC rejects short name registration (404)", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx: AppContext, _payload: Uint8Array) => {
      return new TextEncoder().encode("{}");
    });
    app.command("generateArticle", handler);
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.news.generateArticle", [], new Uint8Array());
    expect(res.status).toBe(404);
  });

  it("XRPC resolves context from authorization header", async () => {
    let capturedCtx: AppContext | undefined;
    const mockHost = createMockHostImports({
      authnResolveContext: () => ({
        claims: {
          'userId': "user-123",
          'sessionId': "sess-1",
          'orgId': "org-abc",
          'orgPermissions': [],
          'issuedAtMs': 0,
          'expiresAtMs': 0,
          issuer: "clerk",
          'authorizedParties': [],
        },
        'targetOrgId': "org-abc",
      }),
    });
    const app = new App(createMockAppDef(), mockHost);
    app.command("com.etzhayyim.apps.test.testCmd", (ctx, _payload) => {
      capturedCtx = ctx;
      return new TextEncoder().encode("{}");
    });
    await app.handleXRPC("/xrpc/com.etzhayyim.apps.test.testCmd", [
      ["authorization", "Bearer test-jwt"],
      ["x-etzhayyim-org-id", "org-abc"],
    ], new Uint8Array());

    expect(capturedCtx?.orgId).toBe("org-abc");
    expect(capturedCtx?.userId).toBe("user-123");
  });
});
