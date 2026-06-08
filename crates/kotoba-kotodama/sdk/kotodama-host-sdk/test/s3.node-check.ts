/**
 * Standalone `node --test` verification for src/s3.ts — runs without the
 * (currently uninstalled) vitest toolchain, using Node's built-in type
 * stripping + node:test + node:assert. Mirrors test/s3.test.ts.
 *
 *   node --test test/s3.node-check.ts
 *
 * The SigV4 cross-check derives the expected signature INDEPENDENTLY with
 * node:crypto, reading back the X-Amz-Date the implementation actually
 * used (no clock stubbing needed).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac, createHash } from "node:crypto";
import { s3Get, s3Put, s3Head, s3Delete, type S3Env } from "../src/s3.ts";

// ── independent SigV4 reference ────────────────────────────────────────
const sha256Hex = (s: string) => createHash("sha256").update(s, "utf8").digest("hex");
const hmac = (key: Buffer | string, msg: string) => createHmac("sha256", key).update(msg, "utf8").digest();
const uriEncode = (s: string, encodeSlash: boolean) =>
  s.split("").map((c) =>
    /[A-Za-z0-9\-_.~]/.test(c) ? c : c === "/" && !encodeSlash ? c : encodeURIComponent(c).toUpperCase(),
  ).join("");

function expectedSignature(o: {
  method: string; endpoint: string; bucket: string; key: string;
  region: string; service: string; secretKey: string; amzDate: string;
}): string {
  const url = new URL(`${o.endpoint}/${o.bucket}/${o.key}`);
  const dateStamp = o.amzDate.slice(0, 8);
  const payloadHash = sha256Hex("");
  const headers: Record<string, string> = {
    host: url.host, "x-amz-content-sha256": payloadHash, "x-amz-date": o.amzDate,
  };
  const names = Object.keys(headers).sort();
  const canonicalHeaders = names.map((n) => `${n}:${headers[n]}\n`).join("");
  const canonicalRequest = [
    o.method, uriEncode(url.pathname, false), "", canonicalHeaders, names.join(";"), payloadHash,
  ].join("\n");
  const scope = `${dateStamp}/${o.region}/${o.service}/aws4_request`;
  const stringToSign = ["AWS4-HMAC-SHA256", o.amzDate, scope, sha256Hex(canonicalRequest)].join("\n");
  const kSigning = hmac(hmac(hmac(hmac("AWS4" + o.secretKey, dateStamp), o.region), o.service), "aws4_request");
  return hmac(kSigning, stringToSign).toString("hex");
}

// ── mocked fetch ───────────────────────────────────────────────────────
let captured: { url: string; init: RequestInit }[] = [];
function mockFetch(make: () => Response) {
  captured = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    captured.push({ url: String(url), init });
    return make();
  }) as any;
}
const authParts = (h: string) => ({
  cred: /Credential=([^,]+)/.exec(h)?.[1] ?? "",
  signed: /SignedHeaders=([^,]+)/.exec(h)?.[1] ?? "",
  sig: /Signature=([0-9a-f]+)/.exec(h)?.[1] ?? "",
});

const CANON: S3Env = {
  S3_ENDPOINT: "https://s3.us-east-1.example.com", S3_REGION: "us-east-1",
  S3_BUCKET: "etzhayyim-cdn", S3_ACCESS_KEY_ID: "AKIDEXAMPLE",
  S3_SECRET_ACCESS_KEY: "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
};
const B2: S3Env = {
  B2_ENDPOINT: "https://s3.us-east-005.backblazeb2.com", B2_REGION: "us-east-005",
  B2_BUCKET: "etzhayyim-cache", B2_KEY_ID: "00bbexamplekeyid",
  B2_APPLICATION_KEY: "K005exampleapplicationkey",
};

test("SigV4 signature matches independent node:crypto derivation (GET)", async () => {
  mockFetch(() => new Response("hello", { status: 200 }));
  await s3Get(CANON, "blobs/abc123");
  const h = captured[0].init.headers as Record<string, string>;
  const { cred, signed, sig } = authParts(h.Authorization);
  assert.equal(signed, "host;x-amz-content-sha256;x-amz-date");
  assert.match(cred, /^AKIDEXAMPLE\/\d{8}\/us-east-1\/s3\/aws4_request$/);
  assert.equal(sig, expectedSignature({
    method: "GET", endpoint: CANON.S3_ENDPOINT!, bucket: CANON.S3_BUCKET!, key: "blobs/abc123",
    region: "us-east-1", service: "s3", secretKey: CANON.S3_SECRET_ACCESS_KEY!, amzDate: h["X-Amz-Date"],
  }));
});

test("request targets bucket/key path + sets amz headers", async () => {
  mockFetch(() => new Response(null, { status: 404 }));
  await s3Get(CANON, "blobs/abc123");
  const h = captured[0].init.headers as Record<string, string>;
  assert.equal(captured[0].url, "https://s3.us-east-1.example.com/etzhayyim-cdn/blobs/abc123");
  assert.equal(h["X-Amz-Content-Sha256"], sha256Hex(""));
});

test("s3Put sends body + content-type, signs content-type", async () => {
  mockFetch(() => new Response(null, { status: 200, headers: { etag: '"deadbeef"' } }));
  const res = await s3Put(CANON, "img/cat.jpg", new Uint8Array([1, 2, 3]), { contentType: "image/jpeg" });
  assert.equal(captured[0].init.method, "PUT");
  assert.deepEqual(new Uint8Array(captured[0].init.body as ArrayBuffer), new Uint8Array([1, 2, 3]));
  const h = captured[0].init.headers as Record<string, string>;
  assert.equal(h["Content-Type"], "image/jpeg");
  assert.equal(authParts(h.Authorization).signed, "content-type;host;x-amz-content-sha256;x-amz-date");
  assert.equal(res.etag, '"deadbeef"');
});

test("s3Get 404→null, 200→parsed", async () => {
  mockFetch(() => new Response(null, { status: 404 }));
  assert.equal(await s3Get(CANON, "missing"), null);
  mockFetch(() => new Response("payload-bytes", {
    status: 200, headers: { "content-length": "13", "content-type": "video/mp4", etag: '"v1"' },
  }));
  const got = await s3Get(CANON, "vid/clip.mp4");
  assert.ok(got);
  assert.equal(got!.size, 13);
  assert.equal(got!.contentType, "video/mp4");
  assert.equal(await got!.text(), "payload-bytes");
});

test("s3Head 404→null, 200→size/type", async () => {
  mockFetch(() => new Response(null, { status: 404 }));
  assert.equal(await s3Head(CANON, "missing"), null);
  mockFetch(() => new Response(null, { status: 200, headers: { "content-length": "1048576", "content-type": "video/mp4" } }));
  assert.deepEqual(await s3Head(CANON, "vid/clip.mp4"), { size: 1048576, etag: null, contentType: "video/mp4" });
});

test("s3Delete idempotent on 404/204, throws on 500", async () => {
  mockFetch(() => new Response(null, { status: 404 }));
  await s3Delete(CANON, "gone");
  mockFetch(() => new Response(null, { status: 204 }));
  await s3Delete(CANON, "ok");
  mockFetch(() => new Response("boom", { status: 500 }));
  await assert.rejects(() => s3Delete(CANON, "err"), /s3Delete/);
});

test("legacy B2_* env honoured as fallback (B2 = one S3 endpoint)", async () => {
  mockFetch(() => new Response(null, { status: 200 }));
  await s3Put(B2, "k", "v");
  const { cred } = authParts((captured[0].init.headers as Record<string, string>).Authorization);
  assert.equal(captured[0].url, "https://s3.us-east-005.backblazeb2.com/etzhayyim-cache/k");
  assert.match(cred, /^00bbexamplekeyid\/\d{8}\/us-east-005\/s3\/aws4_request$/);
});

test("missing config throws a clear error", async () => {
  await assert.rejects(
    () => s3Get({ S3_REGION: "us-east-1" } as S3Env, "k"),
    /missing S3_ENDPOINT.*S3_BUCKET.*S3_ACCESS_KEY_ID.*S3_SECRET_ACCESS_KEY/,
  );
});
