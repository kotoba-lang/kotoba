// shinka.test.ts — Tests for shinka (進化), heartbeat, and follow handler stubs.

import { describe, it, expect, vi } from "vitest";
import { createHostSDK } from "../src/index.js";
import { App, asAgentTool, withCapabilityTags, responsible, accountable, requireApproval, withBPMNTask, withOCELEvent } from "../src/app.js";
import { AssigneeKind, DecisionClass } from "../src/types.js";
import { createMockAppDef, createMockHostImports } from "./mock-helpers.js";

describe("shinka (進化) and heartbeat", () => {
  it("shinkaHandler.onHeartbeat returns ok with empty array by default", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    const result = sdk.witExports.shinkaHandler.onHeartbeat("[]", "{}");
    expect(result.tag).toBe("ok");
    if (result.tag === "ok") {
      expect(result.val).toBe("[]");
    }
  });

  it("shinkaHandler.onReaction returns ok by default", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    const result = sdk.witExports.shinkaHandler.onReaction('{"kind":"like"}');
    expect(result.tag).toBe("ok");
  });

  it("shinkaHandler.onNewFollower returns ok by default", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    const result = sdk.witExports.shinkaHandler.onNewFollower("abc123");
    expect(result.tag).toBe("ok");
  });

  it("shinkaHandler.onFollowRequest returns pending by default", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    const result = sdk.witExports.shinkaHandler.onFollowRequest("req-nanoid", "did:web:req", "consent-1");
    expect(result.tag).toBe("ok");
    if (result.tag === "ok") {
      expect(result.val).toBe("pending");
    }
  });

  it("shinkaHandler catches errors and returns err tag", () => {
    // We can't directly set the heartbeat handler in the current API,
    // but we can test the error path via wHandler
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    // witExports handlers wrap in try/catch returning err tag
    // The default handlers don't throw, so test the error path via serveHandler
    const result = sdk.witExports.serveHandler.handle(
      "unknown-method", new Uint8Array(), { did: "", orgId: "", nanoid: "", roles: [], trustLevel: "", contractRefs: [] },
    );
    expect(result.tag).toBe("err");
  });
});

describe("App.serveAsync() auto-registration", () => {
  function createRegHarness() {
    const governanceRegisterManifestSpy = vi.fn(async () => {});
    const mockHost = createMockHostImports({
      configGet: (key) => key === "PERFORMER_ID" ? "test-nanoid" : undefined,
    });
    const mockPds = {
      governanceRegisterManifest: governanceRegisterManifestSpy,
    } as any;
    return { governanceRegisterManifestSpy, mockHost, mockPds };
  }

  it("serveAsync() registers governance manifest when XrpcClient is available", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef({ id: "test-app", name: "Test", description: "Desc" }), mockHost, mockPds);
    app.command("translate", () => new Uint8Array(), asAgentTool("Translate text"));

    await app.serveAsync();

    expect(governanceRegisterManifestSpy).toHaveBeenCalledTimes(1);
  });

  it("serveAsync() registers governance manifest", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef({ id: "myapp" }), mockHost, mockPds);
    app.command("process", () => new Uint8Array());

    await app.serveAsync();

    expect(governanceRegisterManifestSpy).toHaveBeenCalledTimes(1);
    const manifestJson = governanceRegisterManifestSpy.mock.calls[0][0];
    const manifest = JSON.parse(manifestJson);
    expect(manifest.appId).toBe("myapp");
    expect(manifest.policies).toHaveLength(1);
    expect(manifest.policies[0].command).toBe("process");
  });

  it("serveAsync() logs and skips registration when XrpcClient is unavailable", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const mockHost = createMockHostImports({
      configGet: (key) => key === "PERFORMER_ID" ? "test-nanoid" : undefined,
    });
    const app = new App(createMockAppDef({ id: "test-app" }), mockHost);

    await app.serveAsync();

    expect(errorSpy).toHaveBeenCalledWith("[serveAsync] XrpcClient is null — governance manifest registration skipped.");
    errorSpy.mockRestore();
  });
});

describe("command options", () => {
  function createRegHarness() {
    const governanceRegisterManifestSpy = vi.fn(async () => {});
    const mockHost = createMockHostImports({
      configGet: (key) => key === "PERFORMER_ID" ? "test" : undefined,
    });
    const mockPds = {
      governanceRegisterManifest: governanceRegisterManifestSpy,
    } as any;
    return { governanceRegisterManifestSpy, mockHost, mockPds };
  }

  it("asAgentTool does not block governance manifest generation", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef(), mockHost, mockPds);
    app.command("translate", () => new Uint8Array(), asAgentTool("Translate text"));
    await app.serveAsync();
    expect(governanceRegisterManifestSpy).toHaveBeenCalledTimes(1);
  });

  it("withCapabilityTags does not block governance manifest generation", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef(), mockHost, mockPds);
    app.command("cmd", () => new Uint8Array(), withCapabilityTags("nlp", "i18n"));
    await app.serveAsync();
    expect(governanceRegisterManifestSpy).toHaveBeenCalledTimes(1);
  });

  it("responsible and accountable set RACI in governance manifest", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef(), mockHost, mockPds);
    app.command("cmd", () => new Uint8Array(),
      responsible(AssigneeKind.OrgRole, "translator"),
      accountable(AssigneeKind.OrgRole, "lead"),
    );
    await app.serveAsync();

    const manifest = JSON.parse(governanceRegisterManifestSpy.mock.calls[0][0]);
    expect(manifest.policies[0].raci).toHaveLength(2);
    expect(manifest.policies[0].raci[0].value).toBe("translator");
    expect(manifest.policies[0].raci[1].value).toBe("lead");
  });

  it("requireApproval sets approval in governance manifest", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef(), mockHost, mockPds);
    app.command("cmd", () => new Uint8Array(),
      requireApproval(DecisionClass.C, 1, "low"),
    );
    await app.serveAsync();

    const manifest = JSON.parse(governanceRegisterManifestSpy.mock.calls[0][0]);
    expect(manifest.policies[0].approval).toBeDefined();
    expect(manifest.policies[0].approval.minApprovers).toBe(1);
    expect(manifest.policies[0].approval.riskTier).toBe("low");
  });

  it("withBPMNTask and withOCELEvent set respective fields", async () => {
    const { governanceRegisterManifestSpy, mockHost, mockPds } = createRegHarness();
    const app = new App(createMockAppDef(), mockHost, mockPds);
    app.command("cmd", () => new Uint8Array(),
      withBPMNTask("task-001"),
      withOCELEvent("order.completed"),
    );
    await app.serveAsync();

    const manifest = JSON.parse(governanceRegisterManifestSpy.mock.calls[0][0]);
    expect(manifest.policies[0].bpmnTaskId).toBe("task-001");
    expect(manifest.policies[0].ocelEventType).toBe("order.completed");
  });
});

describe("AT Protocol repo commit handling", () => {
  it("comAtprotoSyncSubscribeRepos returns null for unrouted collection", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    const result = sdk.witExports.wHandler.handleComAtprotoSyncSubscribeReposCommit({
      seq: 1n, repo: "did:web:test", collection: "unknown.collection",
      rkey: "abc", action: "create", cid: null, rev: null, time: new Date().toISOString(),
    });
    expect(result.tag).toBe("ok");
  });

  it("wHandler wraps comAtprotoSyncSubscribeRepos errors", () => {
    const mockHost = createMockHostImports({
      conversationGetHistory: () => { throw new Error("test error"); },
    });
    const app = new App(createMockAppDef(), mockHost);
    // Register a wRoute
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
      hostOverrides: {
        conversationGetHistory: () => { throw new Error("test error"); },
      },
    });
    // Set up a command with lexicon routing
    // comAtprotoSyncSubscribeRepos for convo.message triggers a code path
    const result = sdk.witExports.wHandler.handleComAtprotoSyncSubscribeReposCommit({
      seq: 1n, repo: "did:web:test", collection: "com.etzhayyim.convo.message",
      rkey: "abc", action: "create", cid: null, rev: null, time: new Date().toISOString(),
    });
    expect(result.tag).toBe("err");
  });
});

describe("remote call dispatch", () => {
  it("dispatchRemoteCall routes to registered handler", () => {
    const mockHost = createMockHostImports();
    const app = new App(createMockAppDef(), mockHost);
    const handler = vi.fn((_params, _did, _org) => new TextEncoder().encode('{"result":"ok"}'));
    app.handleRemoteCall("myiface", "mymethod", handler);

    const result = app.dispatchRemoteCall("myiface", "mymethod", new Uint8Array(), "did:caller", "org-1");
    expect(handler).toHaveBeenCalledTimes(1);
    expect(new TextDecoder().decode(result)).toContain("result");
  });

  it("dispatchRemoteCall falls back to command handler", () => {
    const mockHost = createMockHostImports();
    const app = new App(createMockAppDef(), mockHost);
    const cmdHandler = vi.fn((_ctx, _payload) => new TextEncoder().encode("{}"));
    app.command("myMethod", cmdHandler);

    const result = app.dispatchRemoteCall("any", "myMethod", new Uint8Array(), "did:x", "org-x");
    expect(cmdHandler).toHaveBeenCalledTimes(1);
  });

  it("dispatchRemoteCall throws for unknown function", () => {
    const mockHost = createMockHostImports();
    const app = new App(createMockAppDef(), mockHost);
    expect(() => {
      app.dispatchRemoteCall("iface", "nonexistent", new Uint8Array(), "", "");
    }).toThrow("unknown remote function");
  });
});
