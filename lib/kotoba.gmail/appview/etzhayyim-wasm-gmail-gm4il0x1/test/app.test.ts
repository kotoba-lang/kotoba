// SVELTEKIT-BACKEND-PRESERVED: moved out of svelte/ during the cljs
// migration; not wired to a test runner.
//
// Moved verbatim (only this header comment + the corrected relative import
// path below) from `svelte/test/gmail.test.ts`. Despite living inside the
// SvelteKit project directory and using its `vitest` devDependency, this
// file has no Svelte content: it imports and exercises the production
// Cloudflare Worker facade at `../src/app.ts` directly (health check,
// invalid-JSON handling, XRPC proxying, 404 fallback), mocking
// `global.fetch`. It is backend test coverage, not frontend/route coverage,
// so it was moved rather than deleted along with `svelte/`.
//
// The SvelteKit-specific `vitest.config.ts` and `package.json` (`"test":
// "vitest run"`, the `vitest` devDependency) that used to run this file
// were removed with `svelte/` and were not reproduced here — this
// migration's brief was the frontend (cljs/), not standing up a TS test
// runner for `src/app.ts`. This file is preserved as source and as a
// specification of `src/app.ts`'s intended behavior, but it will not run
// as-is until a `vitest` (or equivalent) config is added back for this
// directory. Reviving that is an open follow-up, not decided here.
import { describe, it, expect, vi } from "vitest";
import app from "../src/app.js";

// Mock global fetch for proxy testing
global.fetch = vi.fn();

describe("gmail appview facade", () => {
  it("returns health check on /health", async () => {
    const req = new Request("https://gmail.etzhayyim.com/health");
    const res = await app.fetch(req, {});
    expect(res.status).toBe(200);
    const data = await res.json() as any;
    expect(data.ok).toBe(true);
    expect(data.actor).toBe("did:web:gmail.etzhayyim.com");
  });

  it("handles invalid json in POST gracefully", async () => {
    const req = new Request("https://gmail.etzhayyim.com/xrpc/com.etzhayyim.apps.gmail.test", {
      method: "POST",
      body: "{ bad json",
    });
    const res = await app.fetch(req, {});
    expect(res.status).toBe(400);
    const data = await res.json() as any;
    expect(data.error).toBe("InvalidJson");
  });

  it("proxies valid XRPC to dispatcher", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(new Response(JSON.stringify({ success: true })));
    const req = new Request("https://gmail.etzhayyim.com/xrpc/com.etzhayyim.apps.gmail.ping");
    const res = await app.fetch(req, {});
    expect(res.status).toBe(200);
    const data = await res.json() as any;
    expect(data.success).toBe(true);
  });

  it("returns 404 for unknown path without ASSETS", async () => {
    const req = new Request("https://gmail.etzhayyim.com/unknown");
    const res = await app.fetch(req, {});
    expect(res.status).toBe(404);
  });
});
