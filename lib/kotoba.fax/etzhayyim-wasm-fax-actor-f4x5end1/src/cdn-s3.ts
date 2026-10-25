// S3-compatible CDN backend — provider-agnostic. All blob reads / writes /
// heads / lists route through aws4fetch SigV4 to {endpoint}/{bucket}/{key}.
// The endpoint/bucket/region are pure config, so this works against any
// S3-compatible store (AWS S3 / Backblaze B2 / Cloudflare R2 / MinIO /
// Linode / Vultr). Backblaze B2 is just one possible endpoint.
//
// Config (canonical S3_* names; legacy B2_* names honoured as a fallback so
// existing Backblaze-wired bindings keep working with no change):
//
//   S3_ENDPOINT          (B2_ENDPOINT)        e.g. s3.us-east-005.backblazeb2.com
//   S3_BUCKET            (B2_BUCKET)
//   S3_REGION            (B2_REGION)
//   S3_ACCESS_KEY_ID     (B2_KEY_ID)
//   S3_SECRET_ACCESS_KEY (B2_APP_KEY)

import { AwsClient } from "aws4fetch";

export interface S3CdnEnv {
  S3_ENDPOINT: string;
  S3_BUCKET: string;
  S3_REGION: string;
  S3_ACCESS_KEY_ID: string;
  S3_SECRET_ACCESS_KEY: string;

  // legacy Backblaze names (honoured as fallback)
  B2_ENDPOINT?: string;
  B2_BUCKET?: string;
  B2_REGION?: string;
  B2_KEY_ID?: string;
  B2_APP_KEY?: string;
}

interface S3CdnConfig {
  endpoint: string;
  bucket: string;
  region: string;
  keyId: string;
  secretKey: string;
}

function resolveConfig(env: Partial<S3CdnEnv>): S3CdnConfig {
  const cfg = {
    endpoint: env.S3_ENDPOINT ?? env.B2_ENDPOINT,
    bucket: env.S3_BUCKET ?? env.B2_BUCKET,
    region: env.S3_REGION ?? env.B2_REGION,
    keyId: env.S3_ACCESS_KEY_ID ?? env.B2_KEY_ID,
    secretKey: env.S3_SECRET_ACCESS_KEY ?? env.B2_APP_KEY,
  };
  const missing = (Object.keys(cfg) as (keyof S3CdnConfig)[]).filter((k) => !cfg[k]);
  if (missing.length > 0) {
    throw new Error(`[cdn-s3] missing config: ${missing.join(",")}`);
  }
  return cfg as S3CdnConfig;
}

function encodeKey(key: string): string {
  return key.split("/").map(encodeURIComponent).join("/");
}

function awsClient(cfg: S3CdnConfig): AwsClient {
  return new AwsClient({
    accessKeyId: cfg.keyId,
    secretAccessKey: cfg.secretKey,
    service: "s3",
    region: cfg.region,
  });
}

function objectUrl(cfg: S3CdnConfig, key: string): string {
  return `https://${cfg.endpoint}/${cfg.bucket}/${encodeKey(key)}`;
}

export async function cdnWrite(
  env: Partial<S3CdnEnv>,
  key: string,
  data: ArrayBuffer,
  contentType: string,
): Promise<void> {
  const cfg = resolveConfig(env);
  const res = await awsClient(cfg).fetch(objectUrl(cfg, key), {
    method: "PUT",
    body: data,
    headers: { "content-type": contentType },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`s3 PUT ${res.status}: ${body.slice(0, 120)}`);
  }
}

export async function cdnRead(
  env: Partial<S3CdnEnv>,
  key: string,
): Promise<{ body: ArrayBuffer; contentType: string } | null> {
  const cfg = resolveConfig(env);
  const res = await awsClient(cfg).fetch(objectUrl(cfg, key), { method: "GET" });
  if (res.status === 404 || res.status === 403) return null;
  if (!res.ok) throw new Error(`s3 GET ${res.status}`);
  return {
    body: await res.arrayBuffer(),
    contentType: res.headers.get("content-type") || "application/octet-stream",
  };
}

// Some S3 stores (incl. B2) return 403 for missing objects (AWS mimicry) when
// the caller lacks list-bucket permission on the prefix. Treat both 403 and
// 404 as "not exists".
export async function cdnHead(
  env: Partial<S3CdnEnv>,
  key: string,
): Promise<{ contentType: string; size: number } | null> {
  const cfg = resolveConfig(env);
  const res = await awsClient(cfg).fetch(objectUrl(cfg, key), { method: "HEAD" });
  if (res.status === 404 || res.status === 403) return null;
  if (!res.ok) throw new Error(`s3 HEAD ${res.status}`);
  const size = Number(res.headers.get("content-length") || "0");
  return {
    contentType: res.headers.get("content-type") || "application/octet-stream",
    size,
  };
}

export interface CdnListResult {
  objects: Array<{ key: string; size: number }>;
  truncated: boolean;
  cursor: string;
}

export async function cdnList(
  env: Partial<S3CdnEnv>,
  prefix: string,
  limit: number,
  cursor?: string,
): Promise<CdnListResult> {
  const cfg = resolveConfig(env);
  const url = new URL(`https://${cfg.endpoint}/${cfg.bucket}`);
  url.searchParams.set("list-type", "2");
  url.searchParams.set("prefix", prefix);
  url.searchParams.set("max-keys", String(Math.max(1, Math.min(1000, limit))));
  if (cursor) url.searchParams.set("continuation-token", cursor);

  const res = await awsClient(cfg).fetch(url.toString(), { method: "GET" });
  if (!res.ok) throw new Error(`s3 LIST ${res.status}`);
  const xml = await res.text();

  const keys: Array<{ key: string; size: number }> = [];
  const keyRe = /<Key>([^<]+)<\/Key>[\s\S]*?<Size>([^<]+)<\/Size>/g;
  let m: RegExpExecArray | null;
  while ((m = keyRe.exec(xml)) !== null) {
    keys.push({ key: m[1]!, size: Number(m[2]) });
  }
  const truncated = /<IsTruncated>true<\/IsTruncated>/.test(xml);
  const nextCursor = /<NextContinuationToken>([^<]+)<\/NextContinuationToken>/.exec(xml)?.[1] ?? "";
  return { objects: keys, truncated, cursor: nextCursor };
}
