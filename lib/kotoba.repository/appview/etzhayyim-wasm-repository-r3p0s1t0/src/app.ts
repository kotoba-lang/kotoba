import {
  asAgentTool,
  createKyselyDb,
  createWorkerExport,
  withCapabilityTags,
  type HostSDK,
  nowISO,
  str,
  nsid,
} from "@etzhayyim/kotodama-host-sdk";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)

/**
 * com.etzhayyim.repository — ADR-0039 Repository-in-Graph.
 *
 * Git object model (blob / tree / commit / ref) over Actor DID. Repository ≡
 * Actor DID (vertex_actor is reused; no vertex_repository entity). Blob / tree
 * / commit are append-only + content-addressed. edge_repository_ref_points is
 * the sole mutable edge — rollback / fast-forward / force all collapse to one
 * edge swap.
 *
 * Lexicons: 00-contracts/lexicons/com/etzhayyim/repository/*.json (12 method + 1 record).
 * Schema:   30-graph/graph-schema/migrations/20260420100000_vertex_repository_tables.ts
 *
 * Phase A/B in this file:
 *   - createBlob / getBlob        : full implementation (Phase A PoC target).
 *   - createTree / getTree         : skeleton.
 *   - createCommit / getCommit     : skeleton (ES256 verify deferred to Phase B).
 *   - createRef / updateRef / listRefs : skeleton.
 *   - log / diff / blame           : skeleton.
 *
 * Phase C (WFP dispatcher + CF Container build runner) and Phase D (WebContainer
 * editor) are separate Workers under 50-infra / yoro.
 */

const ACTOR_NAME = "repository";
const ACTOR_DID = "did:web:repository.etzhayyim.com";
const INLINE_TIER_CUTOFF_BYTES = 16 * 1024;

// ─── Per-isolate recent-write cache (Task 3: Hyperdrive / RisingWave read-after-write lag) ─
// RW barrier_interval = ~5s; a Worker SELECT issued <1s after its own INSERT often
// returns stale. We supplement dedup / existence checks with an in-isolate Set so the
// common "create X then use X" pattern works without waiting a checkpoint.
//
// Bounds: each Set capped at 5,000 entries via FIFO eviction. Per-DID bootstrap
// tracker capped at 1,000 DIDs. Plenty for authoring burst; not a replacement for
// strongly-consistent state.
//
// Task 4: blob content cache mirrors inline-tier bytes so getBlob from the same
// isolate returns bytes immediately without waiting for RW checkpoint (observed
// ~25s lag in Phase A.5 migration 2026-04-20). R2-tier blobs are NOT cached
// (content lives in R2, not memory). Cache eviction is byte-budgeted.
const CACHE_CAP = 5000;
const BLOB_CONTENT_CACHE_BUDGET_BYTES = 10 * 1024 * 1024; // 10 MiB soft cap
const recentBlobs = new Set<string>();
const recentTrees = new Set<string>();
const recentCommits = new Set<string>();
const bootstrapDone = new Set<string>();
// hash → { bytes (base64url), sizeBytes, mimeType|null }
const blobContentCache = new Map<string, { contentB64: string; sizeBytes: number; mimeType: string | null }>();
let blobContentCacheBytes = 0;

function cacheAdd(set: Set<string>, key: string): void {
  if (set.size >= CACHE_CAP) {
    const first = set.values().next().value;
    if (first) set.delete(first);
  }
  set.add(key);
}

function cacheBlobContent(hash: string, contentB64: string, sizeBytes: number, mimeType: string | null): void {
  if (blobContentCache.has(hash)) return;
  // Evict oldest entries (Map preserves insertion order) until budget fits.
  while (blobContentCacheBytes + sizeBytes > BLOB_CONTENT_CACHE_BUDGET_BYTES && blobContentCache.size > 0) {
    const firstKey = blobContentCache.keys().next().value;
    if (!firstKey) break;
    const entry = blobContentCache.get(firstKey);
    if (entry) blobContentCacheBytes -= entry.sizeBytes;
    blobContentCache.delete(firstKey);
  }
  if (sizeBytes > BLOB_CONTENT_CACHE_BUDGET_BYTES) return; // single item too large
  blobContentCache.set(hash, { contentB64, sizeBytes, mimeType });
  blobContentCacheBytes += sizeBytes;
}

// Retry a read once after a short delay — absorbs the common single-barrier lag
// when a commit/tree is looked up right after it was written in a previous request.
async function retryRead<T>(fn: () => Promise<T | null | undefined>, delayMs = 400): Promise<T | null> {
  const first = await fn().catch(() => null);
  if (first) return first as T;
  await new Promise((r) => setTimeout(r, delayMs));
  const second = await fn().catch(() => null);
  return (second ?? null) as T | null;
}

function decodeParams(payload: any): Record<string, any> {
  if (!payload) return {};
  if (typeof payload === "object" && !(payload instanceof Uint8Array)) return payload as any;
  try {
    const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
    if (bytes.length === 0) return {};
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return {};
  }
}

function toUint8(content: unknown): Uint8Array {
  if (content instanceof Uint8Array) return content;
  if (typeof content === "string") {
    // Base64url-encoded per lexicon bytes encoding contract.
    const b64 = content.replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64.length % 4 === 0 ? 0 : 4 - (b64.length % 4);
    const normalized = b64 + "=".repeat(pad);
    const bin = atob(normalized);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  if (Array.isArray(content)) return new Uint8Array(content as number[]);
  return new Uint8Array();
}

function toBase64Url(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const arr = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < arr.length; i++) hex += arr[i].toString(16).padStart(2, "0");
  return hex;
}

// vertex_id follows ADR-0019 path-based DID convention — prefix is the
// OWNING DID, not the repository Worker's service DID. Per ADR-0039 §2
// "Repository ≡ Actor DID" the same content under different DIDs produces
// different vertex_ids (git-faithful: each repo keeps its own object store).
// Cross-owner dedup remains possible via the content-addressed `hash`
// column (not vertex_id) at query time.
function vertexId(owner: string, kind: "blob" | "tree" | "commit" | "ref", key: string): string {
  return `at://${owner}/com.etzhayyim.repository.${kind}/${key}`;
}

function baseVertex(owner: string): Record<string, unknown> {
  const now = new Date();
  return {
    _seq: null,
    created_date: now.toISOString().slice(0, 10),
    sensitivity_ord: 100,
    owner_did: owner,
    created_at: now.toISOString(),
    org_id: "etzhayyim",
    user_id: owner,
    actor_id: owner,
  };
}

function baseEdge(owner: string): Record<string, unknown> {
  const now = new Date();
  return {
    _seq: null,
    created_date: now.toISOString().slice(0, 10),
    sensitivity_ord: 100,
    owner_did: owner,
    created_at: now.toISOString(),
  };
}

// ─── Commit signing helpers (ADR-0039 §3 + ADR-0023 ES256 key reuse) ────
// Commit hash canonical form — git-style text so it is inspectable + deterministic.
// signature_es256 is NEVER part of the hash input; key rotation can re-sign the same hash.
function canonicalCommitText(c: {
  treeHash: string;
  parentHashes: string[];
  authorDid: string;
  committerDid: string;
  message: string;
  authorTimestamp: string;
  committerTimestamp: string;
}): string {
  const parents = c.parentHashes.map((p) => `parent ${p}`).join("\n");
  const head =
    `tree ${c.treeHash}\n` +
    (parents ? parents + "\n" : "") +
    `author ${c.authorDid} ${c.authorTimestamp}\n` +
    `committer ${c.committerDid} ${c.committerTimestamp}\n`;
  return head + "\n" + c.message;
}

// did:web resolver per ADR-0019 path-based DID spec.
//   did:web:host.etzhayyim.com           → https://host.etzhayyim.com/.well-known/did.json
//   did:web:host.etzhayyim.com:a:b:c     → https://host.etzhayyim.com/a/b/c/did.json
function didToDocUrl(did: string): string | null {
  if (!did.startsWith("did:web:")) return null;
  const rest = did.slice("did:web:".length);
  const [host, ...segments] = rest.split(":");
  if (!host) return null;
  return segments.length === 0
    ? `https://${host}/.well-known/did.json`
    : `https://${host}/${segments.join("/")}/did.json`;
}

async function fetchDidDocument(did: string): Promise<any | null> {
  const url = didToDocUrl(did);
  if (!url) return null;
  try {
    const res = await fetch(url, { cf: { cacheTtl: 60 } } as any);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// Extract all P-256 (ES256) JWK public keys from a did doc. ADR-0023 multi-key
// rotation publishes up to 3 entries ([cur, next, prev]); we accept any.
async function loadEs256PublicKeys(didDoc: any): Promise<CryptoKey[]> {
  const methods: any[] = Array.isArray(didDoc?.verificationMethod) ? didDoc.verificationMethod : [];
  const keys: CryptoKey[] = [];
  for (const vm of methods) {
    const jwk = vm?.publicKeyJwk;
    if (!jwk || jwk.kty !== "EC" || jwk.crv !== "P-256") continue;
    try {
      const k = await crypto.subtle.importKey(
        "jwk",
        jwk,
        { name: "ECDSA", namedCurve: "P-256" },
        false,
        ["verify"],
      );
      keys.push(k);
    } catch {
      // Skip malformed entries; others may still verify.
    }
  }
  return keys;
}

function fromB64Url(s: string): Uint8Array {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4 === 0 ? 0 : 4 - (b64.length % 4);
  const bin = atob(b64 + "=".repeat(pad));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

// ─── LCS-based line diff (Phase B-2: unified hunks + blame back-walk) ────
// Simple O(m*n) DP. Adequate for typical source files (< ~5000 lines each).
// For large binary / minified content caller is expected to flag binary upstream.
type DiffChangeKind = "context" | "add" | "delete";
interface DiffChange {
  kind: DiffChangeKind;
  oldLineNo?: number; // 1-indexed
  newLineNo?: number; // 1-indexed
  content: string;
}

function diffLines(oldLines: string[], newLines: string[]): DiffChange[] {
  const m = oldLines.length;
  const n = newLines.length;
  // dp[i][j] = LCS length of oldLines[0..i) and newLines[0..j)
  const dp: Uint32Array[] = new Array(m + 1);
  for (let i = 0; i <= m; i++) dp[i] = new Uint32Array(n + 1);
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) dp[i][j] = dp[i - 1][j - 1] + 1;
      else dp[i][j] = dp[i - 1][j] >= dp[i][j - 1] ? dp[i - 1][j] : dp[i][j - 1];
    }
  }
  const out: DiffChange[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (oldLines[i - 1] === newLines[j - 1]) {
      out.unshift({ kind: "context", oldLineNo: i, newLineNo: j, content: oldLines[i - 1] });
      i--;
      j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      out.unshift({ kind: "delete", oldLineNo: i, content: oldLines[i - 1] });
      i--;
    } else {
      out.unshift({ kind: "add", newLineNo: j, content: newLines[j - 1] });
      j--;
    }
  }
  while (i > 0) {
    out.unshift({ kind: "delete", oldLineNo: i, content: oldLines[i - 1] });
    i--;
  }
  while (j > 0) {
    out.unshift({ kind: "add", newLineNo: j, content: newLines[j - 1] });
    j--;
  }
  return out;
}

interface Hunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: string[]; // prefixed with ' ', '+', or '-'
}

function buildHunks(changes: DiffChange[], context: number): Hunk[] {
  // Indices of non-context changes
  const nonCtx: number[] = [];
  for (let i = 0; i < changes.length; i++) if (changes[i].kind !== "context") nonCtx.push(i);
  if (nonCtx.length === 0) return [];
  if (context < 0) context = changes.length; // -1 → full file

  const hunks: Hunk[] = [];
  let hunkStart = Math.max(0, nonCtx[0] - context);
  let lastChangeIdx = nonCtx[0];

  const emit = (from: number, lastChg: number): void => {
    const to = Math.min(changes.length, lastChg + 1 + context);
    const slice = changes.slice(from, to);
    let oldStart = 0;
    let newStart = 0;
    for (const c of slice) {
      if (oldStart === 0 && c.oldLineNo) oldStart = c.oldLineNo;
      if (newStart === 0 && c.newLineNo) newStart = c.newLineNo;
      if (oldStart && newStart) break;
    }
    let oldLines = 0;
    let newLines = 0;
    const lines: string[] = [];
    for (const c of slice) {
      if (c.kind === "delete" || c.kind === "context") oldLines++;
      if (c.kind === "add" || c.kind === "context") newLines++;
      const prefix = c.kind === "add" ? "+" : c.kind === "delete" ? "-" : " ";
      lines.push(prefix + c.content);
    }
    hunks.push({ oldStart: oldStart || 1, oldLines, newStart: newStart || 1, newLines, lines });
  };

  for (let k = 1; k < nonCtx.length; k++) {
    const idx = nonCtx[k];
    if (idx - lastChangeIdx > context * 2) {
      emit(hunkStart, lastChangeIdx);
      hunkStart = Math.max(0, idx - context);
    }
    lastChangeIdx = idx;
  }
  emit(hunkStart, lastChangeIdx);
  return hunks;
}

// heuristic: > 1% NUL bytes → treat as binary
function isLikelyBinary(bytes: Uint8Array): boolean {
  if (bytes.length === 0) return false;
  let nuls = 0;
  const sample = Math.min(bytes.length, 4096);
  for (let i = 0; i < sample; i++) if (bytes[i] === 0) nuls++;
  return nuls / sample > 0.01;
}

async function verifyCommitSignatureEs256(
  commitHashHex: string,
  signatureB64Url: string,
  authorDid: string,
): Promise<{ ok: boolean; reason?: string }> {
  if (signatureB64Url === "bootstrap") return { ok: true, reason: "bootstrap" };
  const doc = await fetchDidDocument(authorDid);
  if (!doc) return { ok: false, reason: "did doc unreachable" };
  const keys = await loadEs256PublicKeys(doc);
  if (keys.length === 0) return { ok: false, reason: "no P-256 verificationMethod" };
  const sig = fromB64Url(signatureB64Url);
  const data = new TextEncoder().encode(commitHashHex);
  for (const k of keys) {
    try {
      const ok = await crypto.subtle.verify(
        { name: "ECDSA", hash: "SHA-256" },
        k,
        sig,
        data,
      );
      if (ok) return { ok: true };
    } catch {
      // Try next key.
    }
  }
  return { ok: false, reason: "no matching key" };
}

const worker = createWorkerExport((sdk: HostSDK) => {
  const env = sdk.env as any;
  const db = createKyselyDb(env.HYPERDRIVE) as any;

  // ─── createBlob ───────────────────────────────────────────────────
  sdk.app.command(
    nsid("com.etzhayyim.repository.createBlob"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = str(params?.ownerDid ?? "");
      const mimeType = params?.mimeType ? str(params.mimeType) : null;
      if (!ownerDid) return { error: "ownerDid required" };
      if (params?.content == null) return { error: "content required" };

      const bytes = toUint8(params.content);
      const hash = await sha256Hex(bytes);
      const sizeBytes = bytes.length;
      const tier: "inline" | "r2" = sizeBytes > INLINE_TIER_CUTOFF_BYTES ? "r2" : "inline";

      // Dedup check — content-addressed, safe to early-return on hit.
      if (recentBlobs.has(hash)) return { hash, sizeBytes, tier, deduplicated: true };
      const existing = await db
        .selectFrom("vertex_repository_blob" as any)
        .select(["hash" as any])
        .where("hash" as any, "=", hash)
        .limit(1)
        .executeTakeFirst()
        .catch(() => null);
      if (existing) {
        cacheAdd(recentBlobs, hash);
        return { hash, sizeBytes, tier, deduplicated: true };
      }

      let bytesRef: string | null = null;
      let inlineText: string | null = null;
      if (tier === "r2") {
        bytesRef = `repository/blob/${hash}`;
        await env.REPOSITORY_BLOB_R2?.put(bytesRef, bytes).catch((e: any) => {
          console.error(`[createBlob] R2 put failed: ${String(e?.message ?? e)}`);
        });
      } else {
        inlineText = toBase64Url(bytes);
      }

      try {
        await db
          .insertInto("vertex_repository_blob" as any)
          .values({
            vertex_id: vertexId(ownerDid, "blob", hash),
            hash,
            size_bytes: sizeBytes,
            tier,
            inline_text: inlineText,
            bytes_ref: bytesRef,
            mime_type: mimeType,
            ...baseVertex(ownerDid),
          } as any)
          .execute();
      } catch (e: any) {
        const msg = String(e?.message ?? e);
        if (!/duplicate|already exists|pk violation/i.test(msg)) {
          console.error(`[createBlob] insert failed: ${msg.slice(0, 400)}`);
          return { error: `insert failed: ${msg.slice(0, 200)}` };
        }
        cacheAdd(recentBlobs, hash);
        if (tier === "inline" && inlineText) cacheBlobContent(hash, inlineText, sizeBytes, mimeType);
        return { hash, sizeBytes, tier, deduplicated: true };
      }
      cacheAdd(recentBlobs, hash);
      if (tier === "inline" && inlineText) cacheBlobContent(hash, inlineText, sizeBytes, mimeType);
      return { hash, sizeBytes, tier, deduplicated: false };
    },
    asAgentTool("Insert a content-addressed blob (sha256). >16KB tiered to R2; idempotent."),
    withCapabilityTags("repository", "blob", "write"),
  );

  // ─── getBlob ─────────────────────────────────────────────────────
  sdk.app.query(
    nsid("com.etzhayyim.repository.getBlob"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const hash = str(params?.hash ?? "");
      if (!hash) return { error: "hash required" };

      // Cache hit — returns immediately without hitting Hyperdrive, absorbs
      // the ~25s RW checkpoint lag for read-after-write in the same isolate.
      const cached = blobContentCache.get(hash);
      if (cached) {
        return {
          hash,
          sizeBytes: cached.sizeBytes,
          content: cached.contentB64,
          mimeType: cached.mimeType ?? undefined,
        };
      }

      const row = await retryRead(() =>
        db
          .selectFrom("vertex_repository_blob" as any)
          .selectAll()
          .where("hash" as any, "=", hash)
          .limit(1)
          .executeTakeFirst(),
      );
      if (!row) return { error: "BlobNotFound" };

      let bytes: Uint8Array = new Uint8Array();
      const r = row as any;
      let contentB64 = "";
      if (r.tier === "inline" && typeof r.inline_text === "string") {
        contentB64 = String(r.inline_text);
        bytes = toUint8(contentB64);
      } else if (r.tier === "r2" && r.bytes_ref) {
        const obj = await env.REPOSITORY_BLOB_R2?.get(r.bytes_ref).catch(() => null);
        if (obj) {
          const ab = await obj.arrayBuffer();
          bytes = new Uint8Array(ab);
          contentB64 = toBase64Url(bytes);
        }
      }

      // Populate cache on first DB hit so subsequent reads on the same isolate
      // skip Hyperdrive entirely.
      if (r.tier === "inline" && contentB64) {
        cacheBlobContent(hash, contentB64, Number(r.size_bytes ?? bytes.length), r.mime_type ?? null);
      }

      return {
        hash: r.hash,
        sizeBytes: Number(r.size_bytes ?? 0),
        content: contentB64 || toBase64Url(bytes),
        mimeType: r.mime_type ?? undefined,
      };
    },
    asAgentTool("Fetch blob bytes by sha256 hash. Tier transparent. Per-isolate cache absorbs RW checkpoint lag."),
    withCapabilityTags("repository", "blob", "read"),
  );

  // ─── createTree ──────────────────────────────────────────────────
  sdk.app.command(
    nsid("com.etzhayyim.repository.createTree"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = str(params?.ownerDid ?? "");
      const entries = Array.isArray(params?.entries) ? params.entries : null;
      if (!ownerDid) return { error: "ownerDid required" };
      if (!entries) return { error: "entries required" };

      // Canonical sort by path and hash over the canonical form.
      const sorted = [...entries].sort((a: any, b: any) => String(a.path).localeCompare(String(b.path)));
      const canonical = sorted.map((e: any) => `${e.mode} ${e.targetHash} ${e.path}`).join("\n");
      const treeHash = await sha256Hex(new TextEncoder().encode(canonical));
      const paths = new Set<string>();
      for (const e of sorted) {
        if (paths.has(String(e.path))) return { error: "DuplicatePath" };
        paths.add(String(e.path));
      }

      // Idempotent INSERT.
      try {
        await db
          .insertInto("vertex_repository_tree" as any)
          .values({
            vertex_id: vertexId(ownerDid, "tree", treeHash),
            tree_hash: treeHash,
            entry_count: sorted.length,
            ...baseVertex(ownerDid),
          } as any)
          .execute();
        for (const e of sorted) {
          await db
            .insertInto("edge_repository_entry" as any)
            .values({
              edge_id: `${ownerDid}:${treeHash}:${e.path}`,
              src_vid: vertexId(ownerDid, "tree", treeHash),
              dst_vid: vertexId(ownerDid, e.mode === "tree" ? "tree" : "blob", String(e.targetHash)),
              path: String(e.path),
              mode: String(e.mode),
              ...baseEdge(ownerDid),
            } as any)
            .execute()
            .catch(() => {});
        }
      } catch (e: any) {
        const msg = String(e?.message ?? e);
        if (!/duplicate|already exists|pk violation/i.test(msg)) {
          return { error: `insert failed: ${msg.slice(0, 200)}` };
        }
        cacheAdd(recentTrees, treeHash);
        return { treeHash, entryCount: sorted.length, deduplicated: true };
      }
      cacheAdd(recentTrees, treeHash);
      return { treeHash, entryCount: sorted.length, deduplicated: false };
    },
    asAgentTool("Insert a tree (directory snapshot). Canonical-sorted entries produce idempotent hash."),
    withCapabilityTags("repository", "tree", "write"),
  );

  // ─── getTree ─────────────────────────────────────────────────────
  sdk.app.query(
    nsid("com.etzhayyim.repository.getTree"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const treeHash = str(params?.treeHash ?? "");
      if (!treeHash) return { error: "treeHash required" };

      const row = await db
        .selectFrom("vertex_repository_tree" as any)
        .selectAll()
        .where("tree_hash" as any, "=", treeHash)
        .limit(1)
        .executeTakeFirst()
        .catch(() => null);
      if (!row) return { error: "TreeNotFound" };

      const treeOwnerDid = String((row as any).owner_did ?? "");
      const entryRows = await db
        .selectFrom("edge_repository_entry" as any)
        .selectAll()
        .where("src_vid" as any, "=", vertexId(treeOwnerDid, "tree", treeHash))
        .execute()
        .catch(() => [] as any[]);

      const entries = entryRows.map((e: any) => ({
        path: e.path,
        mode: e.mode,
        targetHash: String(e.dst_vid).split("/").pop() ?? "",
      }));

      return { treeHash, entries, truncated: false };
    },
    asAgentTool("Fetch a tree and its canonical-sorted entry list."),
    withCapabilityTags("repository", "tree", "read"),
  );

  // ─── createCommit (Phase B: full ES256 verify via did.json) ──────
  sdk.app.command(
    nsid("com.etzhayyim.repository.createCommit"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const treeHash = str(params?.treeHash ?? "");
      const authorDid = str(params?.authorDid ?? "");
      const committerDid = str(params?.committerDid ?? authorDid);
      const message = str(params?.message ?? "");
      const signatureEs256 = str(params?.signatureEs256 ?? "");
      const parentHashes: string[] = Array.isArray(params?.parentHashes)
        ? params.parentHashes.map((p: any) => String(p))
        : [];
      const authorTimestamp = str(params?.timestamp ?? nowISO());
      const committerTimestamp = nowISO();

      if (!treeHash || !authorDid || !message || !signatureEs256) {
        return { error: "treeHash, authorDid, message, signatureEs256 required" };
      }

      // Verify referenced tree exists. Use recent-write cache + single retry to
      // absorb RisingWave checkpoint lag (~5s barrier) for the common "create
      // tree then create commit" pattern.
      let treeFound = recentTrees.has(treeHash);
      if (!treeFound) {
        const treeRow = await retryRead(() =>
          db
            .selectFrom("vertex_repository_tree" as any)
            .select(["tree_hash" as any])
            .where("tree_hash" as any, "=", treeHash)
            .limit(1)
            .executeTakeFirst(),
        );
        treeFound = !!treeRow;
      }
      if (!treeFound) return { error: "MissingTree" };

      // Verify referenced parents exist.
      for (const p of parentHashes) {
        if (recentCommits.has(p)) continue;
        const parentRow = await retryRead(() =>
          db
            .selectFrom("vertex_repository_commit" as any)
            .select(["commit_hash" as any])
            .where("commit_hash" as any, "=", p)
            .limit(1)
            .executeTakeFirst(),
        );
        if (!parentRow) return { error: "MissingParent", missing: p };
      }

      const canonical = canonicalCommitText({
        treeHash,
        parentHashes,
        authorDid,
        committerDid,
        message,
        authorTimestamp,
        committerTimestamp,
      });
      const commitHash = await sha256Hex(new TextEncoder().encode(canonical));

      // Bootstrap: first-commit-per-DID guard. Previously a best-effort check
      // against RisingWave (up to ~25s checkpoint lag could let a second
      // bootstrap slip through). Now backed by D1's serializable PRIMARY KEY
      // constraint — INSERT succeeds exactly once per author_did, future
      // attempts hit UNIQUE violation and reject.
      if (signatureEs256 === "bootstrap") {
        if (bootstrapDone.has(authorDid)) {
          return { error: "InvalidSignature", detail: "bootstrap only allowed for first commit per DID" };
        }
        const d1 = (env as any).REPOSITORY_CAS_D1 as D1Database | undefined;
        if (d1) {
          // Strongly-consistent guard. commitHash is computed below but we
          // only need the PK lock here; use a sentinel and UPDATE with the
          // real hash after the canonical hash is available.
          const guardAt = nowISO();
          try {
            const res = await d1
              .prepare("INSERT INTO bootstrap_first_commit (author_did, commit_hash, recorded_at) VALUES (?1, ?2, ?3) ON CONFLICT(author_did) DO NOTHING")
              .bind(authorDid, "pending", guardAt)
              .run();
            // D1 returns meta.changes=0 when ON CONFLICT DO NOTHING fired.
            const changes = Number((res as any)?.meta?.changes ?? (res as any)?.changes ?? 0);
            if (changes === 0) {
              cacheAdd(bootstrapDone, authorDid);
              return { error: "InvalidSignature", detail: "bootstrap already consumed for this DID (D1 guard)" };
            }
          } catch (e: any) {
            console.error(`[createCommit] D1 bootstrap guard failed, falling back to RW: ${String(e?.message ?? e).slice(0, 200)}`);
          }
        }
        // Fallback: RW check (eventually consistent). Keeps guard when D1
        // binding is missing, reproduces previous behaviour.
        const existing = await db
          .selectFrom("edge_repository_authored_by" as any)
          .select(["edge_id" as any])
          .where("dst_vid" as any, "=", authorDid)
          .limit(1)
          .executeTakeFirst()
          .catch(() => null);
        if (existing) {
          cacheAdd(bootstrapDone, authorDid);
          return { error: "InvalidSignature", detail: "bootstrap only allowed for first commit per DID" };
        }
      } else {
        const verify = await verifyCommitSignatureEs256(commitHash, signatureEs256, authorDid);
        if (!verify.ok) return { error: "InvalidSignature", detail: verify.reason ?? "" };
      }

      // Idempotent INSERT — commit_hash is deterministic from content so retry-safe.
      let deduplicated = false;
      try {
        await db
          .insertInto("vertex_repository_commit" as any)
          .values({
            vertex_id: vertexId(authorDid, "commit", commitHash),
            commit_hash: commitHash,
            tree_hash: treeHash,
            author_did: authorDid,
            committer_did: committerDid,
            message,
            author_timestamp: authorTimestamp,
            committer_timestamp: committerTimestamp,
            signature_es256: signatureEs256,
            ...baseVertex(authorDid),
          } as any)
          .execute();
      } catch (e: any) {
        const msg = String(e?.message ?? e);
        if (/duplicate|already exists|pk violation/i.test(msg)) {
          deduplicated = true;
        } else {
          return { error: `insert failed: ${msg.slice(0, 200)}` };
        }
      }

      if (!deduplicated) {
        // Edges — idempotent on PK (edge_id is deterministic).
        await db
          .insertInto("edge_repository_tree" as any)
          .values({
            edge_id: `${authorDid}:commit-tree:${commitHash}`,
            src_vid: vertexId(authorDid, "commit", commitHash),
            dst_vid: vertexId(authorDid, "tree", treeHash),
            ...baseEdge(authorDid),
          } as any)
          .execute()
          .catch(() => {});
        await db
          .insertInto("edge_repository_authored_by" as any)
          .values({
            edge_id: `${authorDid}:commit-author:${commitHash}`,
            src_vid: vertexId(authorDid, "commit", commitHash),
            dst_vid: authorDid,
            role: "author",
            ...baseEdge(authorDid),
          } as any)
          .execute()
          .catch(() => {});
        for (let i = 0; i < parentHashes.length; i++) {
          await db
            .insertInto("edge_repository_parent" as any)
            .values({
              edge_id: `${authorDid}:commit-parent:${commitHash}:${i}`,
              src_vid: vertexId(authorDid, "commit", commitHash),
              dst_vid: vertexId(authorDid, "commit", parentHashes[i]),
              parent_ordinal: i,
              ...baseEdge(authorDid),
            } as any)
            .execute()
            .catch(() => {});
        }
      }
      cacheAdd(recentCommits, commitHash);
      if (signatureEs256 === "bootstrap") {
        cacheAdd(bootstrapDone, authorDid);
        // Update D1 sentinel with real commit_hash.
        const d1 = (env as any).REPOSITORY_CAS_D1 as D1Database | undefined;
        if (d1) {
          await d1
            .prepare("UPDATE bootstrap_first_commit SET commit_hash = ?1 WHERE author_did = ?2 AND commit_hash = 'pending'")
            .bind(commitHash, authorDid)
            .run()
            .catch(() => {});
        }
      }

      return { commitHash, committerTimestamp, deduplicated };
    },
    asAgentTool("Insert a signed commit object. ES256 signature verified via author DID's did.json."),
    withCapabilityTags("repository", "commit", "write"),
  );

  // ─── getCommit (Phase B: server-side signatureValid check) ───────
  sdk.app.query(
    nsid("com.etzhayyim.repository.getCommit"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const commitHash = str(params?.commitHash ?? "");
      if (!commitHash) return { error: "commitHash required" };

      const row = await db
        .selectFrom("vertex_repository_commit" as any)
        .selectAll()
        .where("commit_hash" as any, "=", commitHash)
        .limit(1)
        .executeTakeFirst()
        .catch(() => null);
      if (!row) return { error: "CommitNotFound" };

      const commitOwnerDid = String((row as any).owner_did ?? (row as any).author_did ?? "");
      const parentRows = await db
        .selectFrom("edge_repository_parent" as any)
        .selectAll()
        .where("src_vid" as any, "=", vertexId(commitOwnerDid, "commit", commitHash))
        .orderBy("parent_ordinal" as any, "asc")
        .execute()
        .catch(() => [] as any[]);
      const parentHashes = parentRows.map(
        (e: any) => String(e.dst_vid).split("/").pop() ?? "",
      );

      const r = row as any;
      let signatureValid = false;
      if (r.signature_es256 === "bootstrap") {
        signatureValid = true;
      } else {
        const verify = await verifyCommitSignatureEs256(
          String(r.commit_hash),
          String(r.signature_es256),
          String(r.author_did),
        );
        signatureValid = verify.ok;
      }

      return {
        commitHash: r.commit_hash,
        treeHash: r.tree_hash,
        parentHashes,
        authorDid: r.author_did,
        committerDid: r.committer_did,
        message: r.message,
        authorTimestamp: r.author_timestamp,
        committerTimestamp: r.committer_timestamp,
        signatureEs256: r.signature_es256,
        signatureValid,
      };
    },
    asAgentTool("Fetch a commit object. Server re-verifies ES256 signature against author did.json."),
    withCapabilityTags("repository", "commit", "read"),
  );

  // ─── Ref layer ────────────────────────────────────────────────────
  // Ref id convention: `${ownerDid}|${refName}` (uniqueness per DID×name).
  // vertex_id follows the at:// convention for consistency with other vertices.
  const refVertexId = (owner: string, name: string): string =>
    `at://${owner}/com.etzhayyim.repository.ref/${encodeURIComponent(name)}`;

  sdk.app.command(
    nsid("com.etzhayyim.repository.createRef"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = str(params?.ownerDid ?? "");
      const refName = str(params?.refName ?? "");
      const kind = str(params?.kind ?? "branch");
      const initialCommit = str(params?.initialCommit ?? "");
      const description = params?.description ? str(params.description) : null;
      if (!ownerDid || !refName || !initialCommit) {
        return { error: "ownerDid, refName, initialCommit required" };
      }
      if (!["branch", "tag", "head"].includes(kind)) {
        return { error: "kind must be branch|tag|head" };
      }
      if (refName === "HEAD" && kind !== "head") {
        return { error: "ReservedName", detail: "'HEAD' reserved for kind=head" };
      }

      // Verify referenced commit exists (with lag tolerance).
      if (!recentCommits.has(initialCommit)) {
        const row = await retryRead(() =>
          db
            .selectFrom("vertex_repository_commit" as any)
            .select(["commit_hash" as any])
            .where("commit_hash" as any, "=", initialCommit)
            .limit(1)
            .executeTakeFirst(),
        );
        if (!row) return { error: "CommitNotFound" };
      }

      const vid = refVertexId(ownerDid, refName);
      const now = nowISO();

      try {
        await db
          .insertInto("vertex_repository_ref" as any)
          .values({
            vertex_id: vid,
            ref_name: refName,
            kind,
            head_commit_hash: initialCommit,
            description,
            ...baseVertex(ownerDid),
            updated_at: now,
          } as any)
          .execute();
      } catch (e: any) {
        const msg = String(e?.message ?? e);
        if (/duplicate|already exists|pk violation/i.test(msg)) {
          return { error: "RefAlreadyExists" };
        }
        return { error: `insert failed: ${msg.slice(0, 200)}` };
      }

      // First ref_points edge = audit log entry for "created".
      await db
        .insertInto("edge_repository_ref_points" as any)
        .values({
          edge_id: `ref-points:${ownerDid}:${refName}:${now}`,
          src_vid: vid,
          dst_vid: vertexId(ownerDid, "commit", initialCommit),
          update_kind: "created",
          reason: null,
          pushed_at: now,
          committer_did: ownerDid,
          ...baseEdge(ownerDid),
        } as any)
        .execute()
        .catch(() => {});
      await db
        .insertInto("edge_repository_ref_owner" as any)
        .values({
          edge_id: `ref-owner:${ownerDid}:${refName}`,
          src_vid: vid,
          dst_vid: ownerDid,
          ...baseEdge(ownerDid),
        } as any)
        .execute()
        .catch(() => {});

      // D1 authoritative head index (strongly consistent mirror of head_commit_hash).
      const d1Create = (env as any).REPOSITORY_CAS_D1 as D1Database | undefined;
      if (d1Create) {
        await d1Create
          .prepare("INSERT INTO ref_head (owner_did, ref_name, head_commit_hash, kind, updated_at) VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(owner_did, ref_name) DO UPDATE SET head_commit_hash = excluded.head_commit_hash, kind = excluded.kind, updated_at = excluded.updated_at")
          .bind(ownerDid, refName, initialCommit, kind, now)
          .run()
          .catch((e: any) => console.error(`[createRef] D1 ref_head insert failed (non-fatal): ${String(e?.message ?? e).slice(0, 200)}`));
      }

      return {
        refId: vid,
        ownerDid,
        refName,
        kind,
        headCommitHash: initialCommit,
      };
    },
    asAgentTool("Create a branch / tag / head ref pointing to an initial commit."),
    withCapabilityTags("repository", "ref", "write"),
  );

  // updateRef: sole mutable write in ADR-0039. CAS on expectedCurrent, ancestry
  // classification (fastForward / rolledBack / forcePushed), firehose stub.
  sdk.app.command(
    nsid("com.etzhayyim.repository.updateRef"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = str(params?.ownerDid ?? "");
      const refName = str(params?.refName ?? "");
      const expectedCurrent = params?.expectedCurrent ? str(params.expectedCurrent) : null;
      const newCommit = str(params?.newCommit ?? "");
      const force = !!params?.force;
      const reason = params?.reason ? str(params.reason) : null;
      if (!ownerDid || !refName || !newCommit) {
        return { error: "ownerDid, refName, newCommit required" };
      }

      const vid = refVertexId(ownerDid, refName);
      const d1 = (env as any).REPOSITORY_CAS_D1 as D1Database | undefined;

      // Prefer D1 for authoritative head read (strongly consistent). Fall back
      // to RisingWave if D1 binding absent or row not yet mirrored.
      let previous: string | null = null;
      let refKind: string | null = null;
      if (d1) {
        const row = (await d1
          .prepare("SELECT head_commit_hash, kind FROM ref_head WHERE owner_did = ?1 AND ref_name = ?2 LIMIT 1")
          .bind(ownerDid, refName)
          .first()) as any;
        if (row) {
          previous = String(row.head_commit_hash ?? "");
          refKind = String(row.kind ?? "branch");
        }
      }
      if (previous === null) {
        const refRow = (await db
          .selectFrom("vertex_repository_ref" as any)
          .selectAll()
          .where("vertex_id" as any, "=", vid)
          .limit(1)
          .executeTakeFirst()
          .catch(() => null)) as any;
        if (!refRow) return { error: "RefNotFound" };
        previous = String(refRow.head_commit_hash ?? "");
        refKind = String(refRow.kind ?? "branch");
      }
      if (refKind === "tag") return { error: "ImmutableRef" };

      if (expectedCurrent !== null && expectedCurrent !== previous) {
        return { error: "RefOutOfDate", actualCurrent: previous };
      }
      if (newCommit === previous) {
        return { error: "NoOp", headCommitHash: previous };
      }

      // Verify newCommit exists.
      if (!recentCommits.has(newCommit)) {
        const c = await retryRead(() =>
          db
            .selectFrom("vertex_repository_commit" as any)
            .select(["commit_hash" as any])
            .where("commit_hash" as any, "=", newCommit)
            .limit(1)
            .executeTakeFirst(),
        );
        if (!c) return { error: "CommitNotFound" };
      }

      // Classify update by walking commit ancestry.
      const isAncestor = async (anc: string, desc: string, maxSteps = 500): Promise<boolean> => {
        if (anc === desc) return true;
        const visited = new Set<string>();
        const queue: string[] = [desc];
        let steps = 0;
        while (queue.length && steps < maxSteps) {
          const cur = queue.shift()!;
          if (visited.has(cur)) continue;
          visited.add(cur);
          steps++;
          const parents = await db
            .selectFrom("edge_repository_parent" as any)
            .select(["dst_vid" as any])
            .where("src_vid" as any, "=", vertexId(ownerDid, "commit", cur))
            .execute()
            .catch(() => [] as any[]);
          for (const p of parents) {
            const ph = String((p as any).dst_vid).split("/").pop() ?? "";
            if (ph === anc) return true;
            if (!visited.has(ph)) queue.push(ph);
          }
        }
        return false;
      };

      let updateKind: "fastForward" | "rolledBack" | "forcePushed";
      if (await isAncestor(previous, newCommit)) {
        updateKind = "fastForward";
      } else if (await isAncestor(newCommit, previous)) {
        updateKind = "rolledBack";
      } else {
        updateKind = "forcePushed";
      }

      if (updateKind === "forcePushed" && !force) {
        return { error: "ForceRequired" };
      }
      if ((updateKind === "rolledBack" || updateKind === "forcePushed") && !reason) {
        return { error: "ReasonRequired" };
      }

      const now = nowISO();

      // D1 CAS: authoritative swap of ref head. If another writer raced us
      // between the SELECT above and here, the WHERE head_commit_hash = ?
      // clause ensures we only win when we're still current.
      if (d1) {
        const casRes = await d1
          .prepare("UPDATE ref_head SET head_commit_hash = ?1, updated_at = ?2 WHERE owner_did = ?3 AND ref_name = ?4 AND head_commit_hash = ?5")
          .bind(newCommit, now, ownerDid, refName, previous)
          .run()
          .catch((e: any) => {
            console.error(`[updateRef] D1 CAS failed: ${String(e?.message ?? e).slice(0, 200)}`);
            return null;
          });
        const casChanged = Number((casRes as any)?.meta?.changes ?? 0);
        if (casRes && casChanged === 0) {
          // Another writer won — fetch real current, reject.
          const fresh = await d1
            .prepare("SELECT head_commit_hash FROM ref_head WHERE owner_did = ?1 AND ref_name = ?2")
            .bind(ownerDid, refName)
            .first()
            .catch(() => null) as any;
          return {
            error: "RefOutOfDate",
            actualCurrent: fresh?.head_commit_hash ?? previous,
            detail: "concurrent updateRef won CAS",
          };
        }
      }

      // UPDATE vertex_repository_ref.head_commit_hash — the authoritative pointer.
      await db
        .updateTable("vertex_repository_ref" as any)
        .set({ head_commit_hash: newCommit, updated_at: now } as any)
        .where("vertex_id" as any, "=", vid)
        .execute()
        .catch((e: any) => {
          console.error(`[updateRef] vertex_ref UPDATE failed: ${String(e?.message ?? e)}`);
        });

      // Append audit row to edge_repository_ref_points (immutable history).
      await db
        .insertInto("edge_repository_ref_points" as any)
        .values({
          edge_id: `ref-points:${ownerDid}:${refName}:${now}`,
          src_vid: vid,
          dst_vid: vertexId(ownerDid, "commit", newCommit),
          update_kind: updateKind,
          reason,
          pushed_at: now,
          committer_did: ownerDid,
          ...baseEdge(ownerDid),
        } as any)
        .execute()
        .catch(() => {});

      // ADR-0036: com.etzhayyim.repository.refUpdate is a domain collection — PDS dispatch
      // removed. Ref state is fully persisted in edge_repository_ref_points above.
      // Firehose broadcast for this collection should be derived via a graph-worker
      // derive rule, not inline PDS dispatch (ADR-0036 §domain write).
      const firehoseCid: string | null = null;

      return {
        ownerDid,
        refName,
        previousCommit: previous,
        newCommit,
        updateKind,
        firehoseCid,
      };
    },
    asAgentTool("Atomic ref pointer rewrite — only mutable write in ADR-0039. CAS + ancestry-based updateKind classification + firehose refUpdate emit."),
    withCapabilityTags("repository", "ref", "write", "faas-trigger"),
  );

  sdk.app.query(
    nsid("com.etzhayyim.repository.listRefs"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = params?.ownerDid ? str(params.ownerDid) : null;
      const subtreeRootDid = params?.subtreeRootDid ? str(params.subtreeRootDid) : null;
      const kind = params?.kind ? str(params.kind) : null;
      const namePrefix = params?.namePrefix ? str(params.namePrefix) : null;
      const limit = Math.min(Math.max(Number(params?.limit ?? 100), 1), 500);
      const offset = Math.max(Number(params?.offset ?? 0), 0);
      if (!ownerDid && !subtreeRootDid) return { error: "ownerDid or subtreeRootDid required" };
      if (ownerDid && subtreeRootDid) return { error: "ownerDid and subtreeRootDid are mutually exclusive" };

      // MVP: subtree mode treated as owner-scoped (no edge_path_child walk yet —
      // path-DID hierarchy traversal is Phase C). Exact DID mode works fully.
      const scopeDid = (ownerDid ?? subtreeRootDid) as string;

      let q = db
        .selectFrom("vertex_repository_ref" as any)
        .selectAll()
        .where("owner_did" as any, "=", scopeDid);
      if (kind) q = q.where("kind" as any, "=", kind);
      if (namePrefix) q = q.where("ref_name" as any, "like", `${namePrefix}%`);
      let rows: any[] = [];
      let listErr: string | null = null;
      try {
        rows = await q.limit(limit).offset(offset).execute();
      } catch (e: any) {
        listErr = String(e?.message ?? e).slice(0, 300);
      }
      if (listErr) return { error: "list_failed", detail: listErr };

      const refs = rows.map((r: any) => ({
        ownerDid: r.owner_did,
        refName: r.ref_name,
        kind: r.kind,
        headCommitHash: r.head_commit_hash,
        updatedAt: r.updated_at,
      }));

      return { refs, total: refs.length, offset, limit };
    },
    asAgentTool("List refs for a single DID (subtree mode: Phase C — currently treated as owner-scoped)."),
    withCapabilityTags("repository", "ref", "read"),
  );

  // ─── History queries ──────────────────────────────────────────────
  // Helper: resolve start commit from ref or direct commitHash.
  const resolveStartCommit = async (
    ownerDid: string | null,
    startRef: string | null,
    startCommit: string | null,
  ): Promise<string | null> => {
    if (startCommit) return startCommit;
    if (!startRef || !ownerDid) return null;
    try {
      const row = (await db
        .selectFrom("vertex_repository_ref" as any)
        .select(["head_commit_hash" as any])
        .where("owner_did" as any, "=", ownerDid)
        .where("ref_name" as any, "=", startRef)
        .limit(1)
        .executeTakeFirst()) as any;
      return row?.head_commit_hash ? String(row.head_commit_hash) : null;
    } catch (e: any) {
      console.error(`[resolveStartCommit] failed: ${String(e?.message ?? e).slice(0, 200)}`);
      return null;
    }
  };

  const loadCommitRow = async (hash: string): Promise<any | null> =>
    (await db
      .selectFrom("vertex_repository_commit" as any)
      .selectAll()
      .where("commit_hash" as any, "=", hash)
      .limit(1)
      .executeTakeFirst()
      .catch(() => null)) as any;

  const loadParents = async (hash: string): Promise<string[]> => {
    const commitRow = await loadCommitRow(hash);
    if (!commitRow) return [];
    const commitOwner = String((commitRow as any).owner_did ?? (commitRow as any).author_did ?? "");
    const rows = await db
      .selectFrom("edge_repository_parent" as any)
      .select(["dst_vid" as any, "parent_ordinal" as any])
      .where("src_vid" as any, "=", vertexId(commitOwner, "commit", hash))
      .orderBy("parent_ordinal" as any, "asc")
      .execute()
      .catch(() => [] as any[]);
    return rows.map((r: any) => String(r.dst_vid).split("/").pop() ?? "");
  };

  // Flat-tree path resolver (MVP — nested trees in Phase C).
  const resolveBlobAtPath = async (
    commitHash: string,
    path: string,
  ): Promise<string | null> => {
    const commit = await loadCommitRow(commitHash);
    if (!commit) return null;
    const commitOwner = String((commit as any).owner_did ?? (commit as any).author_did ?? "");
    const entries = await db
      .selectFrom("edge_repository_entry" as any)
      .select(["path" as any, "dst_vid" as any])
      .where("src_vid" as any, "=", vertexId(commitOwner, "tree", commit.tree_hash))
      .execute()
      .catch(() => [] as any[]);
    const e = entries.find((r: any) => String(r.path) === path);
    if (!e) return null;
    return String((e as any).dst_vid).split("/").pop() ?? null;
  };

  // Load inline-tier blob as text. Returns null for R2-tier or binary or missing.
  const loadBlobText = async (
    blobHash: string,
  ): Promise<{ text: string; bytes: Uint8Array } | null> => {
    // Cache first — absorbs same-isolate read-after-write lag.
    const cached = blobContentCache.get(blobHash);
    if (cached) {
      const bytes = toUint8(cached.contentB64);
      if (isLikelyBinary(bytes)) return null;
      return { text: new TextDecoder().decode(bytes), bytes };
    }
    const row = (await retryRead(() =>
      db
        .selectFrom("vertex_repository_blob" as any)
        .selectAll()
        .where("hash" as any, "=", blobHash)
        .limit(1)
        .executeTakeFirst(),
    )) as any;
    if (!row) return null;
    if (row.tier === "inline" && typeof row.inline_text === "string") {
      const bytes = toUint8(row.inline_text);
      if (isLikelyBinary(bytes)) return null;
      return { text: new TextDecoder().decode(bytes), bytes };
    }
    return null;
  };

  // True / false: did this commit's tree entry at `path` differ from ANY parent's?
  // Root commits with path present are considered to "touch" the path (introduce it).
  const commitTouchesPath = async (
    commitHash: string,
    parents: string[],
    path: string,
  ): Promise<boolean> => {
    const current = await resolveBlobAtPath(commitHash, path);
    if (parents.length === 0) return current !== null;
    for (const p of parents) {
      const parentBlob = await resolveBlobAtPath(p, path);
      if (parentBlob !== current) return true;
    }
    return false;
  };

  sdk.app.query(
    nsid("com.etzhayyim.repository.log"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = params?.ownerDid ? str(params.ownerDid) : null;
      const startRef = params?.startRef ? str(params.startRef) : null;
      const startCommit = params?.startCommit ? str(params.startCommit) : null;
      const mode = str(params?.mode ?? "firstParent");
      const authorDid = params?.authorDid ? str(params.authorDid) : null;
      const pathFilter = params?.pathFilter ? str(params.pathFilter) : null;
      const limit = Math.min(Math.max(Number(params?.limit ?? 50), 1), 500);
      const cursor = params?.cursor ? str(params.cursor) : null;
      if (!startRef && !startCommit) return { error: "startRef or startCommit required" };
      if (startRef && startCommit) return { error: "InvalidParameters", detail: "startRef and startCommit are mutually exclusive" };

      const head = cursor ?? (await resolveStartCommit(ownerDid, startRef, startCommit));
      if (!head) return { error: startRef ? "RefNotFound" : "CommitNotFound" };

      const out: any[] = [];
      const visited = new Set<string>();
      const queue: string[] = [head];
      let nextCursor: string | null = null;

      while (queue.length && out.length < limit) {
        const cur = queue.shift()!;
        if (visited.has(cur)) continue;
        visited.add(cur);
        const row = await loadCommitRow(cur);
        if (!row) continue;
        const parents = await loadParents(cur);
        let include = true;
        if (authorDid && row.author_did !== authorDid) include = false;
        if (include && pathFilter) {
          include = await commitTouchesPath(cur, parents, pathFilter);
        }
        if (include) {
          out.push({
            commitHash: row.commit_hash,
            treeHash: row.tree_hash,
            parentHashes: parents,
            authorDid: row.author_did,
            committerDid: row.committer_did,
            message: row.message,
            authorTimestamp: row.author_timestamp,
            committerTimestamp: row.committer_timestamp,
            signatureEs256: row.signature_es256,
          });
        }
        if (mode === "firstParent") {
          if (parents[0]) queue.push(parents[0]);
        } else {
          for (const p of parents) queue.push(p);
        }
        if (out.length >= limit && queue.length) {
          nextCursor = queue[0] ?? null;
          break;
        }
      }

      return nextCursor ? { commits: out, cursor: nextCursor } : { commits: out };
    },
    asAgentTool("Walk commit ancestry from a ref or commit (firstParent / fullDag). Supports pathFilter + authorDid filter."),
    withCapabilityTags("repository", "history", "read"),
  );

  // diff: file-level tree diff (MVP — no unified hunks yet; Phase C).
  sdk.app.query(
    nsid("com.etzhayyim.repository.diff"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const baseCommit = str(params?.baseCommit ?? "");
      const headCommit = str(params?.headCommit ?? "");
      const pathPrefix = params?.pathPrefix ? str(params.pathPrefix) : null;
      if (!baseCommit || !headCommit) return { error: "baseCommit and headCommit required" };

      const [baseRow, headRow] = await Promise.all([loadCommitRow(baseCommit), loadCommitRow(headCommit)]);
      if (!baseRow || !headRow) return { error: "CommitNotFound" };

      const flattenTree = async (treeHash: string): Promise<Map<string, { mode: string; hash: string }>> => {
        const out = new Map<string, { mode: string; hash: string }>();
        // Tree may belong to any owner — look up via tree_hash column to discover.
        const treeRow = (await db
          .selectFrom("vertex_repository_tree" as any)
          .select(["owner_did" as any])
          .where("tree_hash" as any, "=", treeHash)
          .limit(1)
          .executeTakeFirst()
          .catch(() => null)) as any;
        if (!treeRow) return out;
        const entries = await db
          .selectFrom("edge_repository_entry" as any)
          .select(["path" as any, "mode" as any, "dst_vid" as any])
          .where("src_vid" as any, "=", vertexId(String(treeRow.owner_did ?? ""), "tree", treeHash))
          .execute()
          .catch(() => [] as any[]);
        for (const e of entries) {
          const path = String((e as any).path);
          const mode = String((e as any).mode);
          const targetHash = String((e as any).dst_vid).split("/").pop() ?? "";
          if (mode === "tree") {
            const nested = await flattenTree(targetHash);
            for (const [np, nv] of nested) out.set(`${path}/${np}`, nv);
          } else {
            out.set(path, { mode, hash: targetHash });
          }
        }
        return out;
      };

      const [baseTree, headTree] = await Promise.all([flattenTree(baseRow.tree_hash), flattenTree(headRow.tree_hash)]);
      const files: any[] = [];
      const paths = new Set<string>([...baseTree.keys(), ...headTree.keys()]);
      const unified = Math.max(-1, Number(params?.unified ?? 3));
      const includeContent = params?.includeContent !== false; // default true

      for (const path of paths) {
        if (pathPrefix && !path.startsWith(pathPrefix)) continue;
        const b = baseTree.get(path);
        const h = headTree.get(path);

        // Compute file-level classification.
        let entry: any = null;
        if (b && h && b.hash !== h.hash) {
          entry = { path, changeKind: "modified", oldBlobHash: b.hash, newBlobHash: h.hash };
        } else if (!b && h) {
          entry = { path, changeKind: "added", newBlobHash: h.hash };
        } else if (b && !h) {
          entry = { path, changeKind: "deleted", oldBlobHash: b.hash };
        } else {
          continue; // unchanged
        }

        // Produce hunks when text + includeContent.
        if (!includeContent) {
          entry.binary = false;
          entry.hunks = [];
          files.push(entry);
          continue;
        }
        const [oldText, newText] = await Promise.all([
          b ? loadBlobText(b.hash) : null,
          h ? loadBlobText(h.hash) : null,
        ]);
        // binary if either side is non-text
        const bothEmpty = !b && !h;
        const anyBinary =
          (b && !oldText) || (h && !newText);
        if (anyBinary || bothEmpty) {
          entry.binary = true;
          entry.hunks = [];
          files.push(entry);
          continue;
        }
        const oldLines = oldText ? oldText.text.split("\n") : [];
        const newLines = newText ? newText.text.split("\n") : [];
        const changes = diffLines(oldLines, newLines);
        const hunks = buildHunks(changes, unified);
        entry.binary = false;
        entry.hunks = hunks;
        files.push(entry);
      }

      return { baseCommit, headCommit, files };
    },
    asAgentTool("Tree diff between two commits — file-level add/modify/delete + unified hunks for text blobs."),
    withCapabilityTags("repository", "history", "read"),
  );

  // blame — true back-walk per-line attribution.
  //
  // Algorithm (naive first-parent blame):
  //   tracked[k] = { originalIdx (1-indexed in HEAD), currentIdx (in blob being analyzed) }
  //   Walk first-parent chain. At each commit whose blob at `path` differs from
  //   parent's, diffLines(parent, current). For each tracked entry: if its
  //   currentIdx maps to an add/new line (no parent counterpart) → attribute to
  //   this commit and drop from tracking; otherwise remap currentIdx to the
  //   parent's line index. At the root (or at first commit where the path is
  //   absent) all remaining tracked lines are attributed.
  //
  // Complexity: O(D × M × N) where D = depth walked, M = current blob lines,
  // N = parent blob lines. MAX_DEPTH cap prevents runaway.
  sdk.app.query(
    nsid("com.etzhayyim.repository.blame"),
    async (_ctx, _p: any) => {
      const params = decodeParams(_p);
      const ownerDid = params?.ownerDid ? str(params.ownerDid) : null;
      const startRef = params?.startRef ? str(params.startRef) : null;
      const startCommit = params?.startCommit ? str(params.startCommit) : null;
      const path = str(params?.path ?? "");
      const lineStart = params?.lineStart ? Number(params.lineStart) : null;
      const lineEnd = params?.lineEnd ? Number(params.lineEnd) : null;
      if (!path) return { error: "path required" };
      if (!startRef && !startCommit) return { error: "startRef or startCommit required" };

      const headCommitHash = await resolveStartCommit(ownerDid, startRef, startCommit);
      if (!headCommitHash) return { error: startRef ? "RefNotFound" : "CommitNotFound" };

      const headBlobHash = await resolveBlobAtPath(headCommitHash, path);
      if (!headBlobHash) return { error: "PathNotFound" };
      const headBlob = await loadBlobText(headBlobHash);
      if (!headBlob) return { error: "BinaryBlob", detail: "R2-tier blob or non-text" };
      const headLines = headBlob.text.split("\n");

      const attribution = new Map<number, string>();
      type Tracked = { originalIdx: number; currentIdx: number };
      let tracked: Tracked[] = headLines.map((_, i) => ({ originalIdx: i, currentIdx: i }));

      const MAX_DEPTH = 500;
      let currentCommit = headCommitHash;
      let currentBlobHash: string | null = headBlobHash;
      let currentLines = headLines;
      let depth = 0;

      const commitAuthor = new Map<string, { authorDid: string; authorTimestamp: string }>();
      const firstRow = await loadCommitRow(headCommitHash);
      if (firstRow) commitAuthor.set(headCommitHash, { authorDid: firstRow.author_did, authorTimestamp: firstRow.author_timestamp });

      while (tracked.length > 0 && depth < MAX_DEPTH) {
        const row = await loadCommitRow(currentCommit);
        if (!row) break;
        if (!commitAuthor.has(currentCommit)) {
          commitAuthor.set(currentCommit, { authorDid: row.author_did, authorTimestamp: row.author_timestamp });
        }

        const parents = await loadParents(currentCommit);
        if (parents.length === 0) {
          for (const t of tracked) attribution.set(t.originalIdx, currentCommit);
          break;
        }
        const parentHash = parents[0];
        const parentBlobHash = await resolveBlobAtPath(parentHash, path);
        if (!parentBlobHash) {
          // Path didn't exist in parent — introduced here.
          for (const t of tracked) attribution.set(t.originalIdx, currentCommit);
          break;
        }
        if (parentBlobHash === currentBlobHash) {
          currentCommit = parentHash;
          depth++;
          continue;
        }
        const parentBlob = await loadBlobText(parentBlobHash);
        if (!parentBlob) break; // binary / unreadable — stop walking, attribute remainder below
        const parentLines = parentBlob.text.split("\n");

        const changes = diffLines(parentLines, currentLines);

        // currentToParent[i] = parent line index (0-based) if current line i is context; else null.
        const currentToParent: (number | null)[] = [];
        let parentCounter = 0;
        for (const c of changes) {
          if (c.kind === "context") {
            currentToParent.push(parentCounter);
            parentCounter++;
          } else if (c.kind === "delete") {
            parentCounter++;
          } else {
            currentToParent.push(null);
          }
        }

        const next: Tracked[] = [];
        for (const t of tracked) {
          const p = currentToParent[t.currentIdx];
          if (p === null || p === undefined) {
            attribution.set(t.originalIdx, currentCommit);
          } else {
            next.push({ originalIdx: t.originalIdx, currentIdx: p });
          }
        }
        tracked = next;

        currentCommit = parentHash;
        currentBlobHash = parentBlobHash;
        currentLines = parentLines;
        depth++;
      }
      // Remainder: attribute to whatever commit we stopped at (best effort).
      for (const t of tracked) {
        if (!attribution.has(t.originalIdx)) attribution.set(t.originalIdx, currentCommit);
      }

      // Ensure author info loaded for every attributed commit.
      const needAuthors = Array.from(new Set(attribution.values())).filter((h) => !commitAuthor.has(h));
      for (const h of needAuthors) {
        const r = await loadCommitRow(h);
        if (r) commitAuthor.set(h, { authorDid: r.author_did, authorTimestamp: r.author_timestamp });
      }

      const startIdx = lineStart ? Math.max(1, lineStart) : 1;
      const endIdx = lineEnd ? Math.min(headLines.length, lineEnd) : headLines.length;
      const lines: any[] = [];
      for (let i = startIdx; i <= endIdx; i++) {
        const attributedCommit = attribution.get(i - 1) ?? headCommitHash;
        const author = commitAuthor.get(attributedCommit) ?? {
          authorDid: "",
          authorTimestamp: "",
        };
        lines.push({
          lineNo: i,
          content: headLines[i - 1] ?? "",
          commitHash: attributedCommit,
          authorDid: author.authorDid,
          authorTimestamp: author.authorTimestamp,
        });
      }

      return { path, blobHash: headBlobHash, lines, walkedDepth: depth };
    },
    asAgentTool("Per-line blame via first-parent back-walk. Line attributed to the commit that introduced it."),
    withCapabilityTags("repository", "history", "read"),
  );

  // Health endpoint for etzhayyim deploy smoke test.
  sdk.app.handleHttp?.("/health", async () =>
    new Response(JSON.stringify({ ok: true, actor: ACTOR_NAME, did: ACTOR_DID, at: nowISO() }), {
      headers: { "content-type": "application/json" },
    }),
  );
});

export default worker;
