/**
 * repository kotoba — git object model: blob → tree → commit → ref.
 *
 * Per ADR-2606011400 (Consensys pattern) + ADR-2605172400 (3-axis OR-test) +
 * ADR-0039 (Repository-in-Graph).
 *
 * SPLIT (this app is (c) mixed — Repository-in-Graph backing Worker):
 *   PUBLIC/FIRST-PARTY (THIS PACKAGE) — the git object model (blob / tree /
 *   commit / ref). A repository is the user's OWN source code held in their OWN
 *   repo (Repository ≡ Actor DID) — first-party content, so the AT PDS record is
 *   the canonical store (the document-editor cluster, code-level). No third-party
 *   PII custody, no settlement, no fulfillment liability on the objects.
 *     → migrated to etzhayyim front (AT PDS records, replaces RW/Hyperdrive).
 *
 *   COMPUTE/HOSTING (STAYS etzhayyim, NOT in this package) — the FaaS build dispatch
 *   (Cloudflare Workers for Platforms) + build execution + serving. Consumed via
 *   consent-capability.
 *
 * AT-Lexicon: no float. Blob size + entry mode are integers; oids are strings.
 *
 * Identity hierarchy:
 *   did:web:repository.etzhayyim.com                       — controller
 *   did:web:repository.etzhayyim.com:blob:{oid}            — a blob
 *   did:web:repository.etzhayyim.com:tree:{oid}            — a tree
 *   did:web:repository.etzhayyim.com:commit:{oid}          — a commit
 *   did:web:repository.etzhayyim.com:ref:{refId}           — a ref
 */

export const REPO_DID_PREFIX = "did:web:repository.etzhayyim.com:" as const;

export const BLOB_COLLECTION = "com.etzhayyim.repository.blob";
export const TREE_COLLECTION = "com.etzhayyim.repository.tree";
export const COMMIT_COLLECTION = "com.etzhayyim.repository.commit";
export const REF_COLLECTION = "com.etzhayyim.repository.ref";

// ─── Enums ──────────────────────────────────────────────────────────

export type EntryType = "blob" | "tree";
export type RefType = "branch" | "tag";

export const ENTRY_TYPES: ReadonlySet<string> = new Set(["blob", "tree"]);
export const REF_TYPES: ReadonlySet<string> = new Set(["branch", "tag"]);

// ─── Blob ───────────────────────────────────────────────────────────

export interface BlobRecord {
  did: string;
  oid: string;
  content: string;
  size: number;
  encoding?: string;
  createdAt: string;
}
export interface BlobView extends BlobRecord {
  blobUri: string;
}
export interface CreateBlobInput {
  oid: string;
  content: string;
  size: number;
  encoding?: string;
}
export interface CreateBlobOutput {
  status: "created" | "alreadyExists" | "rejected";
  blobUri?: string;
  did?: string;
  oid?: string;
  error?: string;
}
export interface GetBlobInput {
  oid: string;
}
export interface GetBlobOutput {
  blob?: BlobView;
  error?: string;
}

// ─── Tree ───────────────────────────────────────────────────────────

export interface TreeEntry {
  name: string;
  type: EntryType;
  oid: string;
  mode: number;
}
export interface TreeRecord {
  did: string;
  oid: string;
  entries: TreeEntry[];
  createdAt: string;
}
export interface TreeView extends TreeRecord {
  treeUri: string;
}
export interface CreateTreeInput {
  oid: string;
  entries: TreeEntry[];
}
export interface CreateTreeOutput {
  status: "created" | "alreadyExists" | "rejected";
  treeUri?: string;
  did?: string;
  oid?: string;
  error?: string;
}
export interface GetTreeInput {
  oid: string;
}
export interface GetTreeOutput {
  tree?: TreeView;
  error?: string;
}

// ─── Commit ─────────────────────────────────────────────────────────

export interface CommitRecord {
  did: string;
  oid: string;
  /** FK → tree. */
  treeOid: string;
  parentOids: string[];
  message: string;
  author?: string;
  committedAt: string;
  createdAt: string;
}
export interface CommitView extends CommitRecord {
  commitUri: string;
}
export interface CreateCommitInput {
  oid: string;
  treeOid: string;
  message: string;
  parentOids?: string[];
  author?: string;
  committedAt?: string;
}
export interface CreateCommitOutput {
  status: "created" | "alreadyExists" | "rejected" | "treeNotFound";
  commitUri?: string;
  did?: string;
  oid?: string;
  error?: string;
}
export interface GetCommitInput {
  oid: string;
}
export interface GetCommitOutput {
  commit?: CommitView;
  error?: string;
}

// ─── Ref ────────────────────────────────────────────────────────────

export interface RefRecord {
  did: string;
  refId: string;
  /** FK → commit. */
  targetOid: string;
  refType: RefType;
  createdAt: string;
  updatedAt: string;
}
export interface RefView extends RefRecord {
  refUri: string;
}
export interface UpdateRefInput {
  refId: string;
  targetOid: string;
  refType?: RefType;
}
export interface UpdateRefOutput {
  status: "updated" | "created" | "rejected" | "commitNotFound";
  refUri?: string;
  did?: string;
  refId?: string;
  error?: string;
}
export interface ListRefsInput {
  refType?: RefType;
  prefix?: string;
  limit?: number;
  cursor?: string;
}
export interface ListRefsOutput {
  items: RefView[];
  cursor?: string;
  total: number;
}

// ─── Coverage ───────────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  blobCount?: number;
  treeCount?: number;
  commitCount?: number;
  refCount?: number;
  refsByType?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isOid(s: string): boolean {
  return /^[0-9a-f]{7,64}$/.test(s);
}

export function blobDidFor(oid: string): string {
  return `${REPO_DID_PREFIX}blob:${oid.toLowerCase()}`;
}
export function blobRkey(oid: string): string {
  return `blob-${oid.toLowerCase()}`;
}
export function treeDidFor(oid: string): string {
  return `${REPO_DID_PREFIX}tree:${oid.toLowerCase()}`;
}
export function treeRkey(oid: string): string {
  return `tree-${oid.toLowerCase()}`;
}
export function commitDidFor(oid: string): string {
  return `${REPO_DID_PREFIX}commit:${oid.toLowerCase()}`;
}
export function commitRkey(oid: string): string {
  return `commit-${oid.toLowerCase()}`;
}
export function refDidFor(refId: string): string {
  return `${REPO_DID_PREFIX}ref:${refId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function refRkey(refId: string): string {
  return `ref-${refId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
