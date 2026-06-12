// lifecycle.test.ts — Tests for createHostSDK() and App lifecycle.

import { describe, it, expect, vi } from "vitest";
import { createHostSDK } from "../src/index.js";
import { App } from "../src/app.js";
import { createMockAppDef, createMockPdsRpc } from "./mock-helpers.js";

describe("createHostSDK", () => {
  it("returns an SDK object with expected shape", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    expect(sdk).toBeDefined();
    expect(sdk.app).toBeInstanceOf(App);
    expect(sdk.pds).toBeDefined();
    expect(sdk.hostImports).toBeDefined();
    expect(sdk.witExports).toBeDefined();
  });

  it("has expected top-level methods", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    expect(typeof sdk.handleRequest).toBe("function");
  });

  it("witExports has all required handlers", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
    });
    expect(typeof sdk.witExports.httpHandler.handle).toBe("function");
    expect(typeof sdk.witExports.wHandler.handleComAtprotoSyncSubscribeReposCommit).toBe("function");
    expect(typeof sdk.witExports.serveHandler.handle).toBe("function");
    expect(typeof sdk.witExports.shinkaHandler.onHeartbeat).toBe("function");
    expect(typeof sdk.witExports.shinkaHandler.onReaction).toBe("function");
    expect(typeof sdk.witExports.shinkaHandler.onNewFollower).toBe("function");
    expect(typeof sdk.witExports.shinkaHandler.onFollowRequest).toBe("function");
  });

  it("configures pds client when pdsRpc is provided", () => {
    const { fetcher } = createMockPdsRpc();
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
      pdsRpc: fetcher,
      internalToken: "test-token",
    });
    expect(sdk.pds).toBeDefined();
  });

  it("reads PERFORMER_DID from env for selfRepo", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: { PERFORMER_DID: "did:web:test.etzhayyim.com" },
    });
    // PERFORMER_DID is in env, so configGet returns it as a string
    expect(sdk.hostImports.configGet("PERFORMER_DID")).toBe("did:web:test.etzhayyim.com");
    expect(sdk).toBeDefined();
  });

  it("reads APP_DID from env as fallback for selfRepo", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: { APP_DID: "did:web:fallback.etzhayyim.com" },
    });
    expect(sdk).toBeDefined();
  });

  it("resolves selfNanoid from PERFORMER_ID config", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef({ id: "fallback-id" }),
      env: { PERFORMER_ID: "abc123" },
    });
    expect(sdk.hostImports.configGet("PERFORMER_ID")).toBe("abc123");
  });

  it("resolves selfNanoid from APP_NANOID when PERFORMER_ID is absent", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef({ id: "fallback-id" }),
      env: { APP_NANOID: "xyz789" },
    });
    expect(sdk.hostImports.configGet("APP_NANOID")).toBe("xyz789");
  });

  it("allows host import overrides", () => {
    const sdk = createHostSDK({
      appDef: createMockAppDef(),
      env: {},
      hostOverrides: {
        configGet: (key: string) => key === "CUSTOM" ? "custom-value" : undefined,
      },
    });
    expect(sdk.hostImports.configGet("CUSTOM")).toBe("custom-value");
  });

});
