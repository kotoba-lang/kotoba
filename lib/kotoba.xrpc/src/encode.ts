// encode.ts — Encoding, hashing, and ID generation utilities (Single Source of Truth).

import { TID } from "@atproto/common-web";

// ── AT Protocol TID (Timestamp ID) ──

let _lastTid: string | undefined;

/** Generate an AT Protocol TID (timestamp-based, base32-sortable, 13 chars).
 *  Guaranteed monotonically increasing within this instance.
 *  Delegates to `@atproto/common-web` `TID.nextStr()` which tracks a per-process
 *  monotonic clock internally; we pass `_lastTid` as an extra guard. */
export function generateTid(): string {
  _lastTid = TID.nextStr(_lastTid);
  return _lastTid;
}

// ── Base64 ──

/** Unicode-safe base64 encode (btoa only handles Latin1). */
export function toBase64(str: string): string {
  return btoa(String.fromCodePoint(...new TextEncoder().encode(str)));
}

// ── FNV-1a 32-bit hash ──

/** FNV-1a 32-bit hash — deterministic ownerHash for GIE SecurityFilter. */
export function fnv1a32(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

// ── SQL value cleaning ──

/** Clean quoted SQL value (strip surrounding quotes). */
export function cl(v: unknown): string {
  return typeof v === "string" ? v.replace(/"/g, "") : String(v ?? "");
}
