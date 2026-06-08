/**
 * Generic S3-compatible blob helpers — Cloudflare Worker-friendly. No
 * external SDK; all S3 SigV4 signing is done with `crypto.subtle`
 * (HMAC-SHA256). Response shape mirrors `R2Bucket` so migration from
 * `env.CDN_R2.get(...)` is mechanical.
 *
 * This is provider-agnostic: it speaks the AWS S3 SigV4 REST API, so it
 * works against any S3-compatible endpoint (AWS S3, Backblaze B2,
 * Cloudflare R2, MinIO, Linode/Vultr Object Storage, …). The endpoint,
 * region and bucket are pure configuration — nothing is hard-coded to a
 * single provider.
 *
 * Env shape (canonical):
 *
 *   S3_ENDPOINT             https://s3.<region>.example.com   (provider URL)
 *   S3_REGION               us-east-1
 *   S3_BUCKET               my-bucket
 *   S3_ACCESS_KEY_ID        (wrangler secret put S3_ACCESS_KEY_ID)
 *   S3_SECRET_ACCESS_KEY    (wrangler secret put S3_SECRET_ACCESS_KEY)
 *   S3_SERVICE              (optional, default "s3")
 *
 * Legacy `B2_*` names are still honoured as a fallback so existing
 * Backblaze-configured deployments keep working without a config change:
 *
 *   B2_ENDPOINT  → S3_ENDPOINT
 *   B2_REGION    → S3_REGION
 *   B2_BUCKET    → S3_BUCKET
 *   B2_KEY_ID            → S3_ACCESS_KEY_ID
 *   B2_APPLICATION_KEY   → S3_SECRET_ACCESS_KEY
 *
 * Usage:
 *
 *   import { s3Get, s3Put, s3Head, s3Delete } from "@etzhayyim/kotodama-host-sdk/s3";
 *   const obj = await s3Get(env, "bim/blobs/abc123");
 *   if (obj) {
 *     const buf = await obj.arrayBuffer();
 *     // ... parse ...
 *   }
 *   await s3Put(env, "bim/meshes/abc123", buf, { contentType: "model/gltf-binary" });
 */

export interface S3Env {
  S3_ENDPOINT?: string;
  S3_REGION?: string;
  S3_BUCKET?: string;
  S3_ACCESS_KEY_ID?: string;
  S3_SECRET_ACCESS_KEY?: string;
  S3_SERVICE?: string;

  // ── legacy Backblaze names (honoured as fallback) ──────────────────
  B2_ENDPOINT?: string;
  B2_REGION?: string;
  B2_BUCKET?: string;
  B2_KEY_ID?: string;
  B2_APPLICATION_KEY?: string;
}

export interface S3GetResult {
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

export interface S3PutOptions {
  contentType?: string;
  cacheControl?: string;
  metadata?: Record<string, string>;
}

export interface S3HeadResult {
  size: number;
  etag: string | null;
  contentType: string | null;
}

interface S3Config {
  endpoint: string;
  region: string;
  bucket: string;
  keyId: string;
  secretKey: string;
  service: string;
  host: string;
}

function readEnv(env: S3Env): S3Config {
  const endpointRaw = env.S3_ENDPOINT ?? env.B2_ENDPOINT;
  const region = env.S3_REGION ?? env.B2_REGION;
  const bucket = env.S3_BUCKET ?? env.B2_BUCKET;
  const keyId = env.S3_ACCESS_KEY_ID ?? env.B2_KEY_ID;
  const secretKey = env.S3_SECRET_ACCESS_KEY ?? env.B2_APPLICATION_KEY;

  const missing: string[] = [];
  if (!endpointRaw) missing.push("S3_ENDPOINT");
  if (!region) missing.push("S3_REGION");
  if (!bucket) missing.push("S3_BUCKET");
  if (!keyId) missing.push("S3_ACCESS_KEY_ID");
  if (!secretKey) missing.push("S3_SECRET_ACCESS_KEY");
  if (missing.length) {
    throw new Error(`s3: not configured — missing ${missing.join(", ")}`);
  }

  const endpoint = endpointRaw!.replace(/\/$/, "");
  const url = new URL(endpoint);
  return {
    endpoint,
    region: region!,
    bucket: bucket!,
    keyId: keyId!,
    secretKey: secretKey!,
    service: env.S3_SERVICE ?? "s3",
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
  secretKey: string;
  service: string;
}

async function signRequest(args: SignArgs): Promise<Record<string, string>> {
  const service = args.service;
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

  const kDate = await hmac(ENC.encode("AWS4" + args.secretKey), dateStamp);
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

function objectUrl(env: S3Env, key: string): { url: URL; cfg: S3Config } {
  const cfg = readEnv(env);
  const url = new URL(`${cfg.endpoint}/${cfg.bucket}/${key.replace(/^\/+/, "")}`);
  return { url, cfg };
}

async function sign(cfg: S3Config, method: SignArgs["method"], url: URL, headers: Record<string, string>, payload: ArrayBuffer | string): Promise<Record<string, string>> {
  return signRequest({
    method, url, headers, payload,
    region: cfg.region, keyId: cfg.keyId, secretKey: cfg.secretKey, service: cfg.service,
  });
}

/**
 * GET an object. Returns `null` on 404 (mirrors `R2Bucket.get` shape).
 * Throws on other non-2xx responses.
 */
export async function s3Get(env: S3Env, key: string): Promise<S3GetResult | null> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await sign(cfg, "GET", url, {}, "");
  const resp = await fetch(url.toString(), { method: "GET", headers });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`s3Get ${key}: ${resp.status} ${await safeText(resp)}`);
  return responseToGetResult(resp);
}

/**
 * HEAD an object. Returns `null` on 404 (mirrors `R2Bucket.head`).
 */
export async function s3Head(env: S3Env, key: string): Promise<S3HeadResult | null> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await sign(cfg, "HEAD", url, {}, "");
  const resp = await fetch(url.toString(), { method: "HEAD", headers });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`s3Head ${key}: ${resp.status} ${await safeText(resp)}`);
  return {
    size: Number(resp.headers.get("content-length") ?? "0"),
    etag: resp.headers.get("etag"),
    contentType: resp.headers.get("content-type"),
  };
}

/**
 * PUT an object. Resolves the SHA-256 hash up front (S3 SigV4 requires
 * `x-amz-content-sha256` of the body, no streaming-unsigned). Returns
 * the etag returned by the store.
 */
export async function s3Put(
  env: S3Env,
  key: string,
  body: ArrayBuffer | Uint8Array | string,
  opts: S3PutOptions = {},
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

  const headers = await sign(cfg, "PUT", url, baseHeaders, payload);
  const resp = await fetch(url.toString(), {
    method: "PUT",
    headers,
    body: payload,
  });
  if (!resp.ok) throw new Error(`s3Put ${key}: ${resp.status} ${await safeText(resp)}`);
  return { etag: resp.headers.get("etag") };
}

/**
 * DELETE an object. Idempotent — 404 is treated as success (the
 * caller's intent was "make sure this is gone").
 */
export async function s3Delete(env: S3Env, key: string): Promise<void> {
  const { url, cfg } = objectUrl(env, key);
  const headers = await sign(cfg, "DELETE", url, {}, "");
  const resp = await fetch(url.toString(), { method: "DELETE", headers });
  if (resp.status === 404) return;
  if (!resp.ok && resp.status !== 204) {
    throw new Error(`s3Delete ${key}: ${resp.status} ${await safeText(resp)}`);
  }
}

// ── helpers ────────────────────────────────────────────────────────────

function responseToGetResult(resp: Response): S3GetResult {
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
