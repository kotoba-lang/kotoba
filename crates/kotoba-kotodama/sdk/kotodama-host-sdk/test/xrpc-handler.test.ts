// xrpc-handler.test.ts — Tests for XRPC handler dispatch, error handling, and SDK request handling.

import { describe, it, expect, vi } from "vitest";
import { createHostSDK } from "../src/index.js";
import { App, withOCELEvent } from "../src/app.js";
import { witToCollection, collectionToLabel, nsidToMethod } from "../src/xrpc-client.js";
import type { AppContext } from "../src/types.js";
import { createMockAppDef, createMockHostImports, createMockPdsRpc } from "./mock-helpers.js";

const HANDOTAI_NS = ["com", "etzhayyim", "apps", "handotai"].join(".");
const HANDOTAI_COMPANY = `${HANDOTAI_NS}.semiconductor-company`;

describe("handleXRPC dispatch", () => {
  function makeApp() {
    return new App(createMockAppDef({ id: "myapp" }), createMockHostImports());
  }

  it("routes full NSID to the correct handler", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx, _p) => new TextEncoder().encode('{"ok":true}'));
    app.command("com.etzhayyim.apps.myapp.processOrder", handler);
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.processOrder", [], new Uint8Array());
    expect(res.status).toBe(200);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("routes full NSID with camelCase method", async () => {
    const app = makeApp();
    const handler = vi.fn((_ctx, _p) => new TextEncoder().encode("{}"));
    app.command("com.etzhayyim.apps.myapp.doSomething", handler);
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.doSomething", [], new Uint8Array());
    expect(res.status).toBe(200);
  });

  it("returns JSON error for unknown methods", async () => {
    const app = makeApp();
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.unknownMethod", [], new Uint8Array());
    expect(res.status).toBe(404);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.error).toContain("unknown xrpc method");
    expect(body.error).toContain("com.etzhayyim.apps.myapp.unknownMethod");
    expect(body.errorCode).toBe("XRPC_UNKNOWN_METHOD");
    expect(body.retryable).toBe(false);
  });

  it("returns 500 with error details on handler throw", async () => {
    const app = makeApp();
    app.command("com.etzhayyim.apps.myapp.explode", () => { throw new Error("kaboom"); });
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.explode", [], new Uint8Array());
    expect(res.status).toBe(500);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.error).toContain("kaboom");
    expect(body.errorCode).toBe("APP_COMMAND_FAILED");
    expect(body.retryable).toBe(true);
  });

  it("content-type header is application/json", async () => {
    const app = makeApp();
    app.command("com.etzhayyim.apps.myapp.test", (_ctx, _p) => new TextEncoder().encode("{}"));
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.test", [], new Uint8Array());
    const ctHeader = res.headers.find(([k]) => k === "content-type");
    expect(ctHeader?.[1]).toBe("application/json");
  });

  it("passes body payload to handler", async () => {
    const app = makeApp();
    let receivedBody: Uint8Array | undefined;
    app.command("com.etzhayyim.apps.myapp.echo", (_ctx, payload) => {
      receivedBody = payload;
      return payload;
    });
    const inputBody = new TextEncoder().encode('{"msg":"hello"}');
    await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.echo", [], inputBody);
    expect(receivedBody).toEqual(inputBody);
  });

  it("emits ocel.v2 start/success for ocel-tagged command", async () => {
    const ocelEmitEvent = vi.fn();
    const host = createMockHostImports({ ocelEmitEvent });
    const app = new App(createMockAppDef({ id: "myapp" }), host);
    app.command(
      "com.etzhayyim.apps.myapp.auditAction",
      () => ({ ok: true }),
      withOCELEvent("audit.action"),
    );
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.auditAction", [], new Uint8Array());
    expect(res.status).toBe(200);
    expect(ocelEmitEvent).toHaveBeenCalledTimes(2);
    const startPayload = JSON.parse(ocelEmitEvent.mock.calls[0][0]);
    const successPayload = JSON.parse(ocelEmitEvent.mock.calls[1][0]);
    expect(startPayload.specVersion).toBe("ocel.v2");
    expect(startPayload.phase).toBe("start");
    expect(successPayload.phase).toBe("success");
    expect(successPayload.status).toBe("ok");
  });

  it("emits ocel.v2 start/success for untagged xrpc command", async () => {
    const ocelEmitEvent = vi.fn();
    const host = createMockHostImports({ ocelEmitEvent });
    const app = new App(createMockAppDef({ id: "myapp" }), host);
    app.command("com.etzhayyim.apps.myapp.plainAction", () => ({ ok: true }));
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.plainAction", [], new Uint8Array());
    expect(res.status).toBe(200);
    expect(ocelEmitEvent).toHaveBeenCalledTimes(2);
    const startPayload = JSON.parse(ocelEmitEvent.mock.calls[0][0]);
    expect(startPayload.eventType).toBe("xrpc.com.etzhayyim.apps.myapp.plainAction");
    expect(startPayload.phase).toBe("start");
  });

  it("emits ocel.v2 error for unknown xrpc method", async () => {
    const ocelEmitEvent = vi.fn();
    const host = createMockHostImports({ ocelEmitEvent });
    const app = new App(createMockAppDef({ id: "myapp" }), host);
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.unknownXrpc", [], new Uint8Array());
    expect(res.status).toBe(404);
    expect(ocelEmitEvent).toHaveBeenCalledTimes(2);
    const errorPayload = JSON.parse(ocelEmitEvent.mock.calls[1][0]);
    expect(errorPayload.eventType).toBe("xrpc.com.etzhayyim.apps.myapp.unknownXrpc");
    expect(errorPayload.phase).toBe("error");
    expect(errorPayload.error.code).toBe("XRPC_UNKNOWN_METHOD");
  });

  it("emits ocel.v2 error on command failure", async () => {
    const ocelEmitEvent = vi.fn();
    const host = createMockHostImports({ ocelEmitEvent });
    const app = new App(createMockAppDef({ id: "myapp" }), host);
    app.command(
      "com.etzhayyim.apps.myapp.failingAuditAction",
      () => {
        const err = new Error("audit-failed");
        (err as Error & { code?: string; status?: number }).code = "AUDIT_FAILED";
        (err as Error & { code?: string; status?: number }).status = 502;
        throw err;
      },
      withOCELEvent("audit.action.failed"),
    );
    const res = await app.handleXRPC("/xrpc/com.etzhayyim.apps.myapp.failingAuditAction", [], new Uint8Array());
    expect(res.status).toBe(502);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.errorCode).toBe("AUDIT_FAILED");
    expect(body.retryable).toBe(true);
    expect(ocelEmitEvent).toHaveBeenCalledTimes(2);
    const errorPayload = JSON.parse(ocelEmitEvent.mock.calls[1][0]);
    expect(errorPayload.phase).toBe("error");
    expect(errorPayload.error.code).toBe("AUDIT_FAILED");
  });
});

describe("SDK handleRequest", () => {
  it("handles a request end-to-end", async () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    sdk.app.command("com.etzhayyim.apps.test.ping", () => new TextEncoder().encode('{"pong":true}'));

    const request = {
      method: "POST",
      url: "https://test.etzhayyim.com/xrpc/com.etzhayyim.apps.test.ping",
      headers: new Headers({ "content-type": "application/json" }),
      body: null,
    };

    const response = await sdk.handleRequest(request);
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.pong).toBe(true);
  });

  it("health endpoint works through handleRequest", async () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });

    const request = {
      method: "GET",
      url: "https://test.etzhayyim.com/health",
      headers: new Headers(),
      body: null,
    };

    const response = await sdk.handleRequest(request);
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("ok");
  });
});

describe("NSID utilities", () => {
  it("witToCollection converts WIT kebab to AT collection", () => {
    expect(witToCollection("etzhayyim:handotai", "article")).toBe("com.etzhayyim.apps.handotai.article");
    expect(witToCollection("etzhayyim:handotai", "semiconductor-company")).toBe(HANDOTAI_COMPANY);
  });

  it("collectionToLabel converts AT collection to SQL label", () => {
    expect(collectionToLabel("com.etzhayyim.apps.handotai.article")).toBe("Article");
    expect(collectionToLabel("com.etzhayyim.apps.handotai.semiconductorCompany")).toBe("SemiconductorCompany");
    expect(collectionToLabel("app.bsky.feed.post")).toBe("Post");
  });

  it("nsidToMethod extracts method from NSID", () => {
    expect(nsidToMethod("com.etzhayyim.apps.handotai.article")).toBe("Article");
    expect(nsidToMethod("app.bsky.feed.getTimeline")).toBe("GetTimeline");
    expect(nsidToMethod("com.atproto.repo.createRecord")).toBe("CreateRecord");
  });
});
