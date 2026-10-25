/**
 * tenso kotoba — Signal E2E secure file transfer, kotoba-E2E split.
 *
 * Per ADR-2606011400 (Consensys) + ADR-2605172400 (3-axis) + ADR-2605181100
 * (kotoba E2E encrypted-record envelope). Founder directive 2026-06-03: PII /
 * CUI / LE may migrate to etzhayyim when made safe via kotoba E2E.
 *
 * SPLIT:
 *   PUBLIC (plaintext AT records) — aggregate transfer stats by status/day:
 *   counts + total bytes, NO DIDs, NO per-transfer rows, NO filenames. This is
 *   the only genuinely-public surface in a zero-knowledge app (mirrors
 *   mv_vertex_tenso_transfer_request_count + statsTenso). Per-transfer existence
 *   + size + timing is itself a metadata leak and therefore is NOT plaintext.
 *
 *   SENSITIVE (kotoba E2E, com.etzhayyim.encrypted.record) — the transfer
 *   envelope (senderDid / recipientDid / filename / mimeType / sizeBytes /
 *   chunkCount / expireAt / maxDownloads / encryptedManifest). This reveals
 *   who-sends-what-to-whom + filenames = confidential, so it is sealed via
 *   sdk.encryptedWrite. Read-cap = owner DID (sender, auto) + recipientDid (the
 *   recipient genuinely holds a read-cap) + any explicit extra recipients. The
 *   substrate never sees this in plaintext.
 *
 *   STAYS etzhayyim (consumed via consent-capability) — B2 chunk blob store/download
 *   EXECUTION; Signal X3DH / prekey-bundle custody (secret custody); download-
 *   limit + revoke ENFORCEMENT (blocking ACTIONS). The regulated *acts*, not the
 *   resulting data records.
 *
 * AT-Lexicon: no float. sizeBytes / chunkCount / maxDownloads are integers
 * (counts/bytes are integral, well under 2^53).
 */

// Plaintext public collection (aggregate stats, no PII).
export const STAT_COLLECTION = "com.etzhayyim.apps.tenso.transferStat";
// E2E inner-type NSID (body shape inside the encrypted envelope).
export const TRANSFER_INNER_TYPE = "com.etzhayyim.apps.tenso.transferEnvelope";

export const TENSO_DID_PREFIX = "did:web:tenso.etzhayyim.com:" as const;

// ─── Transfer stat (PLAINTEXT, public aggregate) ────────────────────

export interface TransferStatRecord {
  did: string;
  statId: string;
  /** Aggregation bucket: status (pending/accepted/...) or a YYYY-MM-DD day. */
  bucket: string;
  transferCount: number;
  totalBytes: number;
  generatedAt: string;
  createdAt: string;
}
export interface TransferStatView extends TransferStatRecord {
  statUri: string;
}
export interface RecordStatInput {
  statId: string;
  bucket: string;
  transferCount: number;
  totalBytes: number;
  generatedAt?: string;
}
export interface RecordStatOutput {
  status: "recorded" | "alreadyExists" | "rejected";
  statUri?: string;
  did?: string;
  statId?: string;
  error?: string;
}
export interface ListStatsInput {
  bucket?: string;
  limit?: number;
  cursor?: string;
}
export interface ListStatsOutput {
  items: TransferStatView[];
  cursor?: string;
  total: number;
}

// ─── Transfer envelope (E2E-ENCRYPTED, CUI) ─────────────────────────

export interface TransferEnvelopeBody {
  transferId: string;
  recipientDid: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  chunkCount: number;
  expireAt: string;
  maxDownloads: number;
  /** signal:v1: wrapped fileKey + chunk CID list (opaque ciphertext). */
  encryptedManifest: string;
}
export interface TransferEnvelopeView extends TransferEnvelopeBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordTransferInput {
  transferId: string;
  recipientDid: string;
  filename: string;
  mimeType?: string;
  sizeBytes: number;
  chunkCount: number;
  expireAt?: string;
  maxDownloads?: number;
  encryptedManifest: string;
  /** Extra DIDs to grant read-cap (owner + recipientDid always included). */
  recipients?: string[];
}
export interface RecordTransferOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  transferId?: string;
  /** Recipient DIDs that received a key-wrap. */
  grantedTo?: string[];
  error?: string;
}
export interface ListTransfersInput {
  recipientDid?: string;
  limit?: number;
  cursor?: string;
}
export interface ListTransfersOutput {
  items: TransferEnvelopeView[];
  cursor?: string;
  total: number;
}
export interface GetTransferInput {
  transferId: string;
}
export interface GetTransferOutput {
  transfer?: TransferEnvelopeView;
  error?: string;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  transferStatCount?: number;
  transferEnvelopeCount?: number;
  statsByBucket?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isPosInt(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n > 0;
}
export function statDidFor(id: string): string {
  return `${TENSO_DID_PREFIX}stat:${id.toLowerCase()}`;
}
export function statRkey(id: string): string {
  return `stat-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function transferRkey(id: string): string {
  return `xfer-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
