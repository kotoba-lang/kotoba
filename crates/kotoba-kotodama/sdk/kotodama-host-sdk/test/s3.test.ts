/**
 * Unit tests for the generic S3-compatible blob helpers (`src/s3.ts`) and
 * the `b2` backward-compat shim (`src/b2.ts`).
 *
 * Verification strategy (no live network / no real credentials):
 *  1. SigV4 correctness — an INDEPENDENT re-implementation of AWS SigV4
 *     using node:crypto recomputes the signature and asserts it matches
 *     the Authorization header s3.ts produced (two implementations
 *     agreeing = real correctness check, not a tautology).
 *  2. Round-trip semantics over a mocked fetch — PUT body/headers, GET
 *     404→null, HEAD size parse, DELETE idempotency.
 *  3. Provider-agnostic config — S3_* canonical env AND legacy B2_*
 *     fallback both work (proves nothing is hard-coded to Backblaze).
 *  4. b2* aliases still resolve to the s3 implementation.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createHmac, createHash } from "node:crypto";
import { s3Get, s3Put, s3Head, s3Delete, type S3Env } from "../src/s3.js";
import { b2Get, b2Put, b2Head, b2Delete } from "../src/b2.js";

// ── independent SigV4 reference (node:crypto) ──────────────────────────
const FIXED_ISO = "2026-04-25T10:15:30.000Z";
const AMZ_DATE = "20260425T101530Z";
const DATE_STAMP = "20260425";

function sha256Hex(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}
function hmac(key: Buffer | string, msg: string): Buffer {
  return createHmac("sha256", key).update(msg, "utf8").digest();
}
function uriEncode(s: string, encodeSlash: boolean): string {
  return s.split("").map((c) => {
    if (/[A-Za-z0-9\-_.~]/.test(c)) return c;
    if (c === "/" && !encodeSlash) return c;
    return encodeURIComponent(c).toUpperCase();
  }).join("");
}

/** Re-derive the expected SigV4 signature for an empty-payload request. */
function expectedSignature(opts: {
  method: string; endpoint: string; bucket: string; key: string;
  region: string; service: string; secretKey: string;
}): string {
  const url = new URL(`${opts.endpoint}/${opts.bucket}/${opts.key}`);
  const payloadHash = sha256Hex(""); // empty body
  const headers: Record<string, string> = {
    host: url.host,
    "x-amz-content-sha256": payloadHash,
    "x-amz-date": AMZ_DATE,
  };
  const names = Object.keys(headers).sort();
  const canonicalHeaders = names.map((n) => `${n}:${headers[n]}\n`).join("");
  const signedHeaders = names.join(";");
  const canonicalRequest = [
    opts.method,
    uriEncode(url.pathname, false),
    "", // no query
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");
  const scope = `${DATE_STAMP}/${opts.region}/${opts.service}/aws4_request`;
  const stringToSign = [
    "AWS4-HMAC-SHA256",
    AMZ_DATE,
    scope,
    sha256Hex(canonicalRequest),
  ].join("\n");
  const kDate = hmac("AWS4" + opts.secretKey, DATE_STAMP);
  const kRegion = hmac(kDate, opts.region);
  const kService = hmac(kRegion, opts.service);
  const kSigning = hmac(kService, "aws4_request");
  return hmac(kSigning, stringToSign).toString("hex");
}

// ── mocked fetch ───────────────────────────────────────────────────────
interface Captured { url: string; init: RequestInit; }
let captured: Captured[];

function mockFetchReturning(make: (call: Captured) => Response) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const call = { url: String(url), init };
    captured.push(call);
    return make(call);
  });
}

const CANON_ENV: S3Env = {
  S3_ENDPOINT: "https://s3.us-east-1.example.com",
  S3_REGION: "us-east-1",
  S3_BUCKET: "etzhayyim-cdn",
  S3_ACCESS_KEY_ID: "AKIDEXAMPLE",
  S3_SECRET_ACCESS_KEY: "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
};

const LEGACY_B2_ENV: S3Env = {
  B2_ENDPOINT: "https://s3.us-east-005.backblazeb2.com",
  B2_REGION: "us-east-005",
  B2_BUCKET: "etzhayyim-cache",
  B2_KEY_ID: "00bbexamplekeyid",
  B2_APPLICATION_KEY: "K005exampleapplicationkey",
};

function authParts(header: string) {
  // AWS4-HMAC-SHA256 Credential=<id>/<scope>, SignedHeaders=<h>, Signature=<sig>
  const cred = /Credential=([^,]+)/.exec(header)?.[1] ?? "";
  const signed = /SignedHeaders=([^,]+)/.exec(header)?.[1] ?? "";
  const sig = /Signature=([0-9a-f]+)/.exec(header)?.[1] ?? "";
  return { cred, signed, sig };
}

beforeEach(() => {
  captured = [];
  vi.useFakeTimers();
  vi.setSystemTime(new Date(FIXED_ISO));
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("s3 SigV4 signing — correctness vs independent reference", () => {
  it("produces a signature matching an independent node:crypto SigV4 derivation (GET)", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response("hello", { status: 200 })) as any;
    await s3Get(CANON_ENV, "blobs/abc123");

    const header = (captured[0].init.headers as Record<string, string>).Authorization;
    const { cred, signed, sig } = authParts(header);

    expect(header.startsWith("AWS4-HMAC-SHA256 ")).toBe(true);
    expect(cred).toBe("AKIDEXAMPLE/20260425/us-east-1/s3/aws4_request");
    expect(signed).toBe("host;x-amz-content-sha256;x-amz-date");
    expect(sig).toBe(expectedSignature({
      method: "GET", endpoint: CANON_ENV.S3_ENDPOINT!, bucket: CANON_ENV.S3_BUCKET!,
      key: "blobs/abc123", region: "us-east-1", service: "s3",
      secretKey: CANON_ENV.S3_SECRET_ACCESS_KEY!,
    }));
  });

  it("sets x-amz-date / x-amz-content-sha256 and signs the bucket/key path", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 404 })) as any;
    await s3Get(CANON_ENV, "blobs/abc123");
    const h = captured[0].init.headers as Record<string, string>;
    expect(h["X-Amz-Date"]).toBe(AMZ_DATE);
    expect(h["X-Amz-Content-Sha256"]).toBe(sha256Hex(""));
    expect(captured[0].url).toBe("https://s3.us-east-1.example.com/etzhayyim-cdn/blobs/abc123");
  });
});

describe("s3 round-trip semantics over mocked fetch", () => {
  it("s3Put sends the body, content-type, and signs content-type", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 200, headers: { etag: '"deadbeef"' } })) as any;
    const res = await s3Put(CANON_ENV, "img/cat.jpg", new Uint8Array([1, 2, 3]), { contentType: "image/jpeg" });

    expect(captured[0].init.method).toBe("PUT");
    expect(new Uint8Array(captured[0].init.body as ArrayBuffer)).toEqual(new Uint8Array([1, 2, 3]));
    const h = captured[0].init.headers as Record<string, string>;
    expect(h["Content-Type"]).toBe("image/jpeg");
    // content-type must be part of the signed header set for a PUT
    expect(authParts(h.Authorization).signed).toBe("content-type;host;x-amz-content-sha256;x-amz-date");
    expect(res.etag).toBe('"deadbeef"');
  });

  it("s3Get returns null on 404, parses metadata on 200", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 404 })) as any;
    expect(await s3Get(CANON_ENV, "missing")).toBeNull();

    globalThis.fetch = mockFetchReturning(() => new Response("payload-bytes", {
      status: 200, headers: { "content-length": "13", "content-type": "video/mp4", etag: '"v1"' },
    })) as any;
    const got = await s3Get(CANON_ENV, "vid/clip.mp4");
    expect(got).not.toBeNull();
    expect(got!.size).toBe(13);
    expect(got!.contentType).toBe("video/mp4");
    expect(await got!.text()).toBe("payload-bytes");
  });

  it("s3Head returns null on 404 and size/type on 200", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 404 })) as any;
    expect(await s3Head(CANON_ENV, "missing")).toBeNull();

    globalThis.fetch = mockFetchReturning(() => new Response(null, {
      status: 200, headers: { "content-length": "1048576", "content-type": "video/mp4" },
    })) as any;
    const head = await s3Head(CANON_ENV, "vid/clip.mp4");
    expect(head).toEqual({ size: 1048576, etag: null, contentType: "video/mp4" });
  });

  it("s3Delete treats 404 and 204 as success, throws on 500", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 404 })) as any;
    await expect(s3Delete(CANON_ENV, "gone")).resolves.toBeUndefined();

    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 204 })) as any;
    await expect(s3Delete(CANON_ENV, "ok")).resolves.toBeUndefined();

    globalThis.fetch = mockFetchReturning(() => new Response("boom", { status: 500 })) as any;
    await expect(s3Delete(CANON_ENV, "err")).rejects.toThrow(/s3Delete/);
  });
});

describe("provider-agnostic config (not hard-coded to Backblaze)", () => {
  it("works with canonical S3_* env against a non-B2 endpoint", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 200 })) as any;
    await s3Put(CANON_ENV, "k", "v");
    expect(captured[0].url).toBe("https://s3.us-east-1.example.com/etzhayyim-cdn/k");
  });

  it("honours legacy B2_* env as a fallback (same code path, B2 = just one S3 endpoint)", async () => {
    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 200 })) as any;
    await s3Put(LEGACY_B2_ENV, "k", "v");
    const { cred } = authParts((captured[0].init.headers as Record<string, string>).Authorization);
    expect(captured[0].url).toBe("https://s3.us-east-005.backblazeb2.com/etzhayyim-cache/k");
    expect(cred).toBe("00bbexamplekeyid/20260425/us-east-005/s3/aws4_request");
  });

  it("throws a clear error listing missing config keys", async () => {
    await expect(s3Get({ S3_REGION: "us-east-1" } as S3Env, "k"))
      .rejects.toThrow(/missing S3_ENDPOINT.*S3_BUCKET.*S3_ACCESS_KEY_ID.*S3_SECRET_ACCESS_KEY/);
  });
});

describe("b2* backward-compat aliases resolve to the s3 implementation", () => {
  it("b2Get/b2Put/b2Head/b2Delete behave identically", async () => {
    expect(b2Get).toBe(s3Get);
    expect(b2Put).toBe(s3Put);
    expect(b2Head).toBe(s3Head);
    expect(b2Delete).toBe(s3Delete);

    globalThis.fetch = mockFetchReturning(() => new Response(null, { status: 200, headers: { etag: '"x"' } })) as any;
    const r = await b2Put(LEGACY_B2_ENV, "legacy/key", "data", { contentType: "image/png" });
    expect(r.etag).toBe('"x"');
    expect(captured[0].url).toBe("https://s3.us-east-005.backblazeb2.com/etzhayyim-cache/legacy/key");
  });
});
