/**
 * B2 (Backblaze B2 S3-compatible) blob fetch helpers — Cloudflare
 * Worker-friendly. No external SDK; all S3 SigV4 signing is done with
 * `crypto.subtle` (HMAC-SHA256). Response shape mirrors `R2Bucket` so
 * migration from `env.CDN_R2.get(...)` is mechanical.
 *
 * ADR-0048 (B2 primary) + `[[conventions]] blob-storage-b2-only`. Use
 * for all new blob-using Workers; existing R2 callers migrate per the
 * `[[migrations]] blob-storage-r2-to-b2-code` recipe.
 *
 * Env shape (all Workers using these helpers):
 *
 *   B2_ENDPOINT             https://s3.us-east-005.backblazeb2.com
 *   B2_REGION               us-east-005
 *   B2_BUCKET               etzhayyim-{actor}
 *   B2_KEY_ID               (wrangler secret put B2_KEY_ID)
 *   B2_APPLICATION_KEY      (wrangler secret put B2_APPLICATION_KEY)
 *
 * Usage:
 *
 *   import { b2Get, b2Put, b2Head, b2Delete } from "@etzhayyim/kotodama-host-sdk";
 *   const obj = await b2Get(env, "bim/blobs/abc123");
 *   if (obj) {
 *     const buf = await obj.arrayBuffer();
 *     // ... parse ...
 *   }
 *   await b2Put(env, "bim/meshes/abc123", buf, { contentType: "model/gltf-binary" });
 */

export interface B2Env {
  B2_ENDPOINT?: string;
  B2_REGION?: string;
  B2_BUCKET?: string;
  B2_KEY_ID?: string;
  B2_APPLICATION_KEY?: string;
}

export interface B2GetResult {
  body: ReadableStream<Uint8Array>;
  arrayBuffer(): Promise<ArrayBuffer>;
  text(): Promise<string>;
  json<T = unknown>(): Promise<T>;
  size: number;
  etag: string | null;
  contentType: string | null;
  /** Raw underlying Response — for streaming pass-through. */
  response: Response;
}

export interface B2PutOptions {
  contentType?: string;
  cacheControl?: string;
  metadata?: Record<string, string>;
}

export interface B2HeadResult {
  size: number;
  etag: string | null;
  contentType: string | null;
}

const REQUIRED: (keyof B2Env)[] = [
  "B2_ENDPOINT", "B2_REGION", "B2_BUCKET", "B2_KEY_ID", "B2_APPLICATION_KEY",
];

function readEnv(env: B2Env): {
  endpoint: string; region: string; bucket: string; keyId: string; appKey: string; host: string;
} {
  for (const k of REQUIRED) {
    if (!env[k]) throw new Error(`b2: ${k} is not configured`);
  }
  const endpoint = env.B2_ENDPOINT!.replace(/\/$/, "");
  const url = new URL(endpoint);
  return {
    endpoint,
    region: env.B2_REGION!,
    bucket: env.B2_BUCKET!,
    keyId: env.B2_KEY_ID!,
    appKey: env.B2_APPLICATION_KEY!,
    host: url.host,
  };
}

// ── S3 SigV4 signing (RFC 4231 HMAC-SHA256 via crypto.subtle) ──────────

const ENC = new TextEncoder();

async function hmac(key: ArrayBuffer | Uint8Array, message: string): Promise<ArrayBuffer> {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    key as BufferSource,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return crypto.subtle.sign("HMAC", cryptoKey, ENC.encode(message));
}

function bufToHex(buf: ArrayBuffer): string {
  const view = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < view.length; i++) s += view[i].toString(16).padStart(2, "0");
  return s;
}

async function sha256Hex(payload: ArrayBuffer | string): Promise<string> {
  const data = typeof payload === "string" ? ENC.encode(payload) : new Uint8Array(payload);
  return bufToHex(await crypto.subtle.digest("SHA-256", data));
}

function uriEncode(s: string, encodeSlash = false): string {
  // S3 SigV4 — RFC 3986 unreserved + skip "/" inside path components.
  return s.split("").map((c) => {
    if (/[A-Za-z0-9\-_.~]/.test(c)) return c;
    if (c === "/" && !encodeSlash) return c;
    return encodeURIComponent(c).toUpperCase();
  }).join("");
}

interface SignArgs {
  method: "GET" | "PUT" | "HEAD" | "DELETE";
  url: URL;
  headers: Record<string, string>;
  payload: ArrayBuffer | string;
  region: string;
  keyId: string;
  appKey: string;
  service?: string;  // default "s3"
}

async function signRequest(args: SignArgs): Promise<Record<string, string>> {
  const service = args.service ?? "s3";
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, ""); // 20260425T101530Z
  const dateStamp = amzDate.slice(0, 8);
  const payloadHash = await sha256Hex(args.payload);

  const canonicalHeadersObj: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(args.headers).map(([k, v]) => [k.toLowerCase().trim(), String(v).trim()]),
    ),
    host: args.url.host,
    "x-amz-content-sha256": payloadHash,
    "x-amz-date": amzDate,
  };
  const sortedHeaderNames = Object.keys(canonicalHeadersObj).sort();
  const canonicalHeaders = sortedHeaderNames.map((n) => `${n}:${canonicalHeadersObj[n]}\n`).join("");
  const signedHeaders = sortedHeaderNames.join(";");

  const canonicalQuery = [...args.url.searchParams.entries()]
    .map(([k, v]) => [uriEncode(k, true), uriEncode(v, true)] as const)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${k}=${v}`)
    .join("&");

  const canonicalRequest = [
    args.method,
    uriEncode(args.url.pathname, false),
    canonicalQuery,
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");

  const credentialScope = `${dateStamp}/${args.region}/${service}/aws4_request`;
  const stringToSign = [
    "AWS4-HMAC-SHA256",
    amzDate,
    credentialScope,
    await sha256Hex(canonicalRequest),
  ].join("\n");

  const kDate = await hmac(ENC.encode("AWS4" + args.appKey), dateStamp);
  const kRegion = await hmac(kDate, args.region);
  const kService = await hmac(kRegion, service);
  const kSigning = await hmac(kService, "aws4_request");
  const signature = bufToHex(await hmac(kSigning, stringToSign));

  return {
    ...args.headers,
    Host: args.url.host,
    "X-Amz-Content-Sha256": payloadHash,
    "X-Amz-Date": amzDate,
    Authorization: `AWS4-HMAC-SHA256 Credential=${args.keyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`,
  };
}

// ── public helpers ─────────────────────────────────────────────────────

function objectUrl(env: B2Env, key: string): { url: URL; cfg: ReturnType<typeof readEnv> } {
  const cfg = readEnv(env);
  const url = new URL(`${cfg.endpoint}/${cfg.bucket}/${key.replace(/^\/+/, "")}`);
  return { url, cfg };
}

/**
 * GET an object. Returns `null` on 404 (mirrors `R2Bucket.get` shape).
 * Throws on other non-2xx responses.
 */
export async function b2Get(env: B2Env, key: string): Promise<B2GetResult | null> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await signRequest({
    method: "GET", url, headers: {}, payload: "",
    region: cfg.region, keyId: cfg.keyId, appKey: cfg.appKey,
  });
  const resp = await fetch(url.toString(), { method: "GET", headers });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`b2Get ${key}: ${resp.status} ${await safeText(resp)}`);
  return responseToGetResult(resp);
}

/**
 * HEAD an object. Returns `null` on 404 (mirrors `R2Bucket.head`).
 */
export async function b2Head(env: B2Env, key: string): Promise<B2HeadResult | null> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await signRequest({
    method: "HEAD", url, headers: {}, payload: "",
    region: cfg.region, keyId: cfg.keyId, appKey: cfg.appKey,
  });
  const resp = await fetch(url.toString(), { method: "HEAD", headers });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`b2Head ${key}: ${resp.status} ${await safeText(resp)}`);
  return {
    size: Number(resp.headers.get("content-length") ?? "0"),
    etag: resp.headers.get("etag"),
    contentType: resp.headers.get("content-type"),
  };
}

/**
 * PUT an object. Resolves the SHA-256 hash up front (S3 SigV4 requires
 * `x-amz-content-sha256` of the body, no streaming-unsigned). Returns
 * the etag returned by B2.
 */
export async function b2Put(
  env: B2Env,
  key: string,
  body: ArrayBuffer | Uint8Array | string,
  opts: B2PutOptions = {},
): Promise<{ etag: string | null }> {
  const { url, cfg } = objectUrl(env, key);
  const payload =
    typeof body === "string"
      ? ENC.encode(body).buffer as ArrayBuffer
      : body instanceof Uint8Array
        ? body.slice().buffer
        : body;

  const baseHeaders: Record<string, string> = {};
  if (opts.contentType) baseHeaders["Content-Type"] = opts.contentType;
  if (opts.cacheControl) baseHeaders["Cache-Control"] = opts.cacheControl;
  if (opts.metadata) {
    for (const [k, v] of Object.entries(opts.metadata)) {
      baseHeaders[`x-amz-meta-${k.toLowerCase()}`] = v;
    }
  }

  const headers = await signRequest({
    method: "PUT", url, headers: baseHeaders, payload,
    region: cfg.region, keyId: cfg.keyId, appKey: cfg.appKey,
  });
  const resp = await fetch(url.toString(), {
    method: "PUT",
    headers,
    body: payload,
  });
  if (!resp.ok) throw new Error(`b2Put ${key}: ${resp.status} ${await safeText(resp)}`);
  return { etag: resp.headers.get("etag") };
}

/**
 * DELETE an object. Idempotent — 404 is treated as success (the
 * caller's intent was "make sure this is gone").
 */
export async function b2Delete(env: B2Env, key: string): Promise<void> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await signRequest({
    method: "DELETE", url, headers: {}, payload: "",
    region: cfg.region, keyId: cfg.keyId, appKey: cfg.appKey,
  });
  const resp = await fetch(url.toString(), { method: "DELETE", headers });
  if (resp.status === 404) return;
  if (!resp.ok && resp.status !== 204) {
    throw new Error(`b2Delete ${key}: ${resp.status} ${await safeText(resp)}`);
  }
}

// ── helpers ────────────────────────────────────────────────────────────

function responseToGetResult(resp: Response): B2GetResult {
  // Tee the body so a caller can do .arrayBuffer() and still walk
  // .response.body if they prefer streaming.
  const [a, b] = resp.body!.tee();
  return {
    body: b,
    arrayBuffer: () => new Response(a).arrayBuffer(),
    text: () => new Response(a).text(),
    json: <T = unknown>() => new Response(a).json() as Promise<T>,
    size: Number(resp.headers.get("content-length") ?? "0"),
    etag: resp.headers.get("etag"),
    contentType: resp.headers.get("content-type"),
    response: resp,
  };
}

async function safeText(resp: Response): Promise<string> {
  try {
    const t = await resp.text();
    return t.length > 300 ? t.slice(0, 300) + "…" : t;
  } catch {
    return "";
  }
}
