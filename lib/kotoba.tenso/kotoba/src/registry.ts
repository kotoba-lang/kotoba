/**
 * tenso kotoba — kotoba-E2E registry.
 *
 * Plaintext path (transferStat): sdk.write / sdk.read — public aggregate stats.
 * E2E path (transferEnvelope): sdk.encryptedWrite / sdk.encryptedRead — the
 * confidential transfer envelope sealed in the kotoba envelope (ADR-2605181100).
 * Read-cap = owner DID (sender, auto) + recipientDid (the recipient holds a
 * read-cap) + explicit extra recipients. The substrate never sees sender/
 * recipient/filename/manifest in plaintext.
 *
 * STAYS etzhayyim (consent-capability): B2 chunk store/download EXECUTION, Signal
 * X3DH/prekey custody, download-limit + revoke ENFORCEMENT.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  STAT_COLLECTION,
  TRANSFER_INNER_TYPE,
  statDidFor,
  statRkey,
  transferRkey,
  isUint,
  isPosInt,
  type CoverageInput,
  type CoverageOutput,
  type GetTransferInput,
  type GetTransferOutput,
  type ListStatsInput,
  type ListStatsOutput,
  type ListTransfersInput,
  type ListTransfersOutput,
  type RecordStatInput,
  type RecordStatOutput,
  type RecordTransferInput,
  type RecordTransferOutput,
  type TransferEnvelopeBody,
  type TransferEnvelopeView,
  type TransferStatRecord,
  type TransferStatView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Transfer stat (PLAINTEXT) ──────────────────────────────────────

export async function recordStat(e: Etzhayyim, input: RecordStatInput): Promise<RecordStatOutput> {
  if (!input.statId || !input.bucket) return { status: "rejected", error: "missingRequiredFields" };
  if (!isUint(input.transferCount)) return { status: "rejected", error: "invalidTransferCount" };
  if (!isUint(input.totalBytes)) return { status: "rejected", error: "invalidTotalBytes" };
  const rkey = statRkey(input.statId);
  const existing = await e.read<TransferStatRecord>({ collection: STAT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", statUri: existing.records[0].uri, did: existing.records[0].value.did, statId: input.statId };
  }
  const now = new Date().toISOString();
  const did = statDidFor(input.statId);
  const record: TransferStatRecord = {
    did,
    statId: input.statId,
    bucket: input.bucket,
    transferCount: input.transferCount,
    totalBytes: input.totalBytes,
    generatedAt: input.generatedAt ?? now,
    createdAt: now,
  };
  const receipt = await e.write({ collection: STAT_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "recorded", statUri: receipt.uri, did, statId: input.statId };
}

export async function listStats(e: Etzhayyim, input: ListStatsInput = {}): Promise<ListStatsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<TransferStatRecord>({ collection: STAT_COLLECTION, cursor: input.cursor, limit });
  const items: TransferStatView[] = resp.records
    .filter((r) => !input.bucket || r.value.bucket === input.bucket)
    .map((r) => ({ ...r.value, statUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Transfer envelope (E2E-ENCRYPTED, CUI) ─────────────────────────

export async function recordTransfer(e: Etzhayyim, input: RecordTransferInput): Promise<RecordTransferOutput> {
  if (!input.transferId || !input.recipientDid || !input.filename) return { status: "rejected", error: "missingRequiredFields" };
  if (!input.encryptedManifest) return { status: "rejected", error: "missingEncryptedManifest" };
  if (!isUint(input.sizeBytes)) return { status: "rejected", error: "invalidSizeBytes" };
  if (!isPosInt(input.chunkCount)) return { status: "rejected", error: "invalidChunkCount" };
  const maxDownloads = input.maxDownloads ?? 10;
  if (!isPosInt(maxDownloads)) return { status: "rejected", error: "invalidMaxDownloads" };

  // senderDid is NOT stored in the body — it is carried by the envelope's
  // `sender` field (set to the owner DID by the substrate on encryptedWrite),
  // surfaced on the view as `sender`. This avoids depending on a non-public
  // `did` accessor on the SDK type.
  const body: TransferEnvelopeBody = {
    transferId: input.transferId,
    recipientDid: input.recipientDid,
    filename: input.filename,
    mimeType: input.mimeType ?? "application/octet-stream",
    sizeBytes: input.sizeBytes,
    chunkCount: input.chunkCount,
    expireAt: input.expireAt ?? new Date(Date.now() + 72 * 3600_000).toISOString(),
    maxDownloads,
    encryptedManifest: input.encryptedManifest,
  };
  // Read-cap = owner DID (sender, auto-wrapped) + recipientDid + extras.
  const recipients = [...new Set([input.recipientDid, ...(input.recipients ?? [])])];
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: TRANSFER_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients,
    rkey: transferRkey(input.transferId),
  });
  return {
    status: "recorded",
    uri: receipt.uri,
    keyId: receipt.keyId,
    transferId: input.transferId,
    grantedTo: receipt.keyWraps.map((w) => w.recipient),
  };
}

async function scanTransfers(e: Etzhayyim, maxScan: number): Promise<TransferEnvelopeView[]> {
  const out: TransferEnvelopeView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<TransferEnvelopeBody>({ innerType: TRANSFER_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listTransfers(e: Etzhayyim, input: ListTransfersInput = {}): Promise<ListTransfersOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanTransfers(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((t) => !input.recipientDid || t.recipientDid === input.recipientDid);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getTransfer(e: Etzhayyim, input: GetTransferInput): Promise<GetTransferOutput> {
  if (!input.transferId) return { error: "invalidTransferId" };
  const all = await scanTransfers(e, DEFAULT_MAX_SCAN);
  const found = all.find((t) => t.transferId === input.transferId);
  if (!found) return { error: "notFound" };
  return { transfer: found };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const statsByBucket: Record<string, number> = {};
  let transferStatCount = 0;
  let cursor: string | undefined;
  while (transferStatCount < maxScan) {
    const page = await e.read<TransferStatRecord>({ collection: STAT_COLLECTION, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      statsByBucket[r.value.bucket] = (statsByBucket[r.value.bucket] ?? 0) + 1;
      transferStatCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const transferEnvelopeCount = (await scanTransfers(e, maxScan)).length;
  return {
    transferStatCount,
    transferEnvelopeCount,
    statsByBucket,
    truncated: transferStatCount >= maxScan || transferEnvelopeCount >= maxScan,
  };
}
