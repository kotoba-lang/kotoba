/**
 * Backward-compatibility shim — `b2*` is now an alias of the generic,
 * provider-agnostic S3 helpers in `./s3`. The blob layer is no longer
 * hard-coded to Backblaze B2; B2 is just one S3-compatible endpoint among
 * many (AWS S3 / R2 / MinIO / Linode / Vultr …). Configure via `S3_*`
 * env vars; the legacy `B2_*` names are still honoured as a fallback
 * (see `./s3`).
 *
 * Prefer importing from "@etzhayyim/kotodama-host-sdk/s3" in new code:
 *
 *   import { s3Get, s3Put, s3Head, s3Delete } from "@etzhayyim/kotodama-host-sdk/s3";
 *
 * Existing `b2Get` / `b2Put` / `b2Head` / `b2Delete` callers keep working
 * unchanged.
 */

import {
  s3Get,
  s3Put,
  s3Head,
  s3Delete,
  type S3Env,
  type S3GetResult,
  type S3PutOptions,
  type S3HeadResult,
} from "./s3.js";

// ── type aliases (legacy names) ────────────────────────────────────────
export type B2Env = S3Env;
export type B2GetResult = S3GetResult;
export type B2PutOptions = S3PutOptions;
export type B2HeadResult = S3HeadResult;

// ── function aliases (legacy names) ────────────────────────────────────
export const b2Get = s3Get;
export const b2Put = s3Put;
export const b2Head = s3Head;
export const b2Delete = s3Delete;

// Re-export the canonical names too, so a `./b2` importer can migrate
// in place without changing the import path.
export { s3Get, s3Put, s3Head, s3Delete };
export type { S3Env, S3GetResult, S3PutOptions, S3HeadResult };
