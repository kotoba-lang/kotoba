/**
 * repository kotoba — git object model registries + coverage.
 * AT PDS records (no RW / no Hyperdrive). Content-addressed:
 *   blob → tree → commit → ref.
 * FK: commit.treeOid → tree; ref.targetOid → commit (validated via exists()).
 * FaaS build dispatch + build execution stay etzhayyim (consent-capability).
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  BLOB_COLLECTION,
  COMMIT_COLLECTION,
  ENTRY_TYPES,
  REF_COLLECTION,
  REF_TYPES,
  TREE_COLLECTION,
  blobDidFor,
  blobRkey,
  commitDidFor,
  commitRkey,
  isOid,
  isUint,
  refDidFor,
  refRkey,
  treeDidFor,
  treeRkey,
  type BlobRecord,
  type CommitRecord,
  type CoverageInput,
  type CoverageOutput,
  type CreateBlobInput,
  type CreateBlobOutput,
  type CreateCommitInput,
  type CreateCommitOutput,
  type CreateTreeInput,
  type CreateTreeOutput,
  type GetBlobInput,
  type GetBlobOutput,
  type GetCommitInput,
  type GetCommitOutput,
  type GetTreeInput,
  type GetTreeOutput,
  type ListRefsInput,
  type ListRefsOutput,
  type RefRecord,
  type RefView,
  type TreeRecord,
  type UpdateRefInput,
  type UpdateRefOutput,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 50_000;

async function exists(e: Etzhayyim, collection: string, rkey: string): Promise<boolean> {
  const resp = await e.read({ collection, rkey }).catch(() => ({ records: [] }));
  return Boolean(resp.records[0]?.value);
}

async function scanAll<T>(e: Etzhayyim, collection: string, maxScan: number, onRow: (v: T) => void): Promise<number> {
  let cursor: string | undefined;
  let scanned = 0;
  while (scanned < maxScan) {
    const page = await e.read<T>({ collection, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      if (scanned >= maxScan) break;
      onRow(r.value);
      scanned += 1;
    }
    if (scanned >= maxScan || !page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return scanned;
}

// ─── Blob ───────────────────────────────────────────────────────────

export async function createBlob(e: Etzhayyim, input: CreateBlobInput): Promise<CreateBlobOutput> {
  if (!input.oid || typeof input.content !== "string") return { status: "rejected", error: "missingRequiredFields" };
  if (!isOid(input.oid)) return { status: "rejected", error: "invalidOid" };
  if (!isUint(input.size)) return { status: "rejected", error: "invalidSize" };
  const rkey = blobRkey(input.oid);
  const existing = await e.read<BlobRecord>({ collection: BLOB_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", blobUri: existing.records[0].uri, did: existing.records[0].value.did, oid: input.oid };
  }
  const did = blobDidFor(input.oid);
  const record: BlobRecord = {
    did,
    oid: input.oid.toLowerCase(),
    content: input.content,
    size: input.size,
    encoding: input.encoding,
    createdAt: new Date().toISOString(),
  };
  const receipt = await e.write({ collection: BLOB_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "created", blobUri: receipt.uri, did, oid: input.oid };
}

export async function getBlob(e: Etzhayyim, input: GetBlobInput): Promise<GetBlobOutput> {
  if (!input.oid) return { error: "invalidOid" };
  const resp = await e.read<BlobRecord>({ collection: BLOB_COLLECTION, rkey: blobRkey(input.oid) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { blob: { ...r.value, blobUri: r.uri } };
}

// ─── Tree ───────────────────────────────────────────────────────────

export async function createTree(e: Etzhayyim, input: CreateTreeInput): Promise<CreateTreeOutput> {
  if (!input.oid || !Array.isArray(input.entries)) return { status: "rejected", error: "missingRequiredFields" };
  if (!isOid(input.oid)) return { status: "rejected", error: "invalidOid" };
  for (const entry of input.entries) {
    if (!entry.name || !entry.oid) return { status: "rejected", error: "invalidEntry" };
    if (!ENTRY_TYPES.has(entry.type)) return { status: "rejected", error: `invalidEntryType:${entry.type}` };
    if (!isUint(entry.mode)) return { status: "rejected", error: "invalidEntryMode" };
  }
  const rkey = treeRkey(input.oid);
  const existing = await e.read<TreeRecord>({ collection: TREE_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", treeUri: existing.records[0].uri, did: existing.records[0].value.did, oid: input.oid };
  }
  const did = treeDidFor(input.oid);
  const record: TreeRecord = {
    did,
    oid: input.oid.toLowerCase(),
    entries: input.entries.map((en) => ({ name: en.name, type: en.type, oid: en.oid.toLowerCase(), mode: en.mode })),
    createdAt: new Date().toISOString(),
  };
  const receipt = await e.write({ collection: TREE_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "created", treeUri: receipt.uri, did, oid: input.oid };
}

export async function getTree(e: Etzhayyim, input: GetTreeInput): Promise<GetTreeOutput> {
  if (!input.oid) return { error: "invalidOid" };
  const resp = await e.read<TreeRecord>({ collection: TREE_COLLECTION, rkey: treeRkey(input.oid) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { tree: { ...r.value, treeUri: r.uri } };
}

// ─── Commit (FK → tree) ─────────────────────────────────────────────

export async function createCommit(e: Etzhayyim, input: CreateCommitInput): Promise<CreateCommitOutput> {
  if (!input.oid || !input.treeOid || !input.message) return { status: "rejected", error: "missingRequiredFields" };
  if (!isOid(input.oid) || !isOid(input.treeOid)) return { status: "rejected", error: "invalidOid" };
  if (!(await exists(e, TREE_COLLECTION, treeRkey(input.treeOid)))) {
    return { status: "treeNotFound", error: `treeNotFound:${input.treeOid}` };
  }
  const rkey = commitRkey(input.oid);
  const existing = await e.read<CommitRecord>({ collection: COMMIT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", commitUri: existing.records[0].uri, did: existing.records[0].value.did, oid: input.oid };
  }
  const now = new Date().toISOString();
  const did = commitDidFor(input.oid);
  const record: CommitRecord = {
    did,
    oid: input.oid.toLowerCase(),
    treeOid: input.treeOid.toLowerCase(),
    parentOids: (input.parentOids ?? []).map((p) => p.toLowerCase()),
    message: input.message,
    author: input.author,
    committedAt: input.committedAt ?? now,
    createdAt: now,
  };
  const receipt = await e.write({ collection: COMMIT_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "created", commitUri: receipt.uri, did, oid: input.oid };
}

export async function getCommit(e: Etzhayyim, input: GetCommitInput): Promise<GetCommitOutput> {
  if (!input.oid) return { error: "invalidOid" };
  const resp = await e.read<CommitRecord>({ collection: COMMIT_COLLECTION, rkey: commitRkey(input.oid) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { commit: { ...r.value, commitUri: r.uri } };
}

// ─── Ref (FK → commit; mutable pointer = the sole atomic write point) ─

export async function updateRef(e: Etzhayyim, input: UpdateRefInput): Promise<UpdateRefOutput> {
  if (!input.refId || !input.targetOid) return { status: "rejected", error: "missingRequiredFields" };
  if (!isOid(input.targetOid)) return { status: "rejected", error: "invalidOid" };
  const refType = input.refType ?? "branch";
  if (!REF_TYPES.has(refType)) return { status: "rejected", error: `invalidRefType:${refType}` };
  if (!(await exists(e, COMMIT_COLLECTION, commitRkey(input.targetOid)))) {
    return { status: "commitNotFound", error: `commitNotFound:${input.targetOid}` };
  }
  const rkey = refRkey(input.refId);
  const now = new Date().toISOString();
  const did = refDidFor(input.refId);
  const existing = await e.read<RefRecord>({ collection: REF_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const createdAt = existing.records[0]?.value?.createdAt ?? now;
  const record: RefRecord = {
    did,
    refId: input.refId,
    targetOid: input.targetOid.toLowerCase(),
    refType,
    createdAt,
    updatedAt: now,
  };
  const receipt = await e.write({ collection: REF_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: existing.records[0]?.value ? "updated" : "created", refUri: receipt.uri, did, refId: input.refId };
}

export async function listRefs(e: Etzhayyim, input: ListRefsInput = {}): Promise<ListRefsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<RefRecord>({ collection: REF_COLLECTION, cursor: input.cursor, limit });
  const prefix = input.prefix?.toLowerCase();
  const items: RefView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.refType && v.refType !== input.refType) return false;
      if (prefix && !v.refId.toLowerCase().startsWith(prefix)) return false;
      return true;
    })
    .map((r) => ({ ...r.value, refUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Coverage ───────────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const refsByType: Record<string, number> = {};
  const blobCount = await scanAll<BlobRecord>(e, BLOB_COLLECTION, maxScan, () => {});
  const treeCount = await scanAll<TreeRecord>(e, TREE_COLLECTION, maxScan, () => {});
  const commitCount = await scanAll<CommitRecord>(e, COMMIT_COLLECTION, maxScan, () => {});
  const refCount = await scanAll<RefRecord>(e, REF_COLLECTION, maxScan, (v) => {
    refsByType[v.refType] = (refsByType[v.refType] ?? 0) + 1;
  });
  return {
    blobCount,
    treeCount,
    commitCount,
    refCount,
    refsByType,
    truncated: blobCount >= maxScan || treeCount >= maxScan || commitCount >= maxScan || refCount >= maxScan,
  };
}
