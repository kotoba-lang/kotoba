/**
 * fax kotoba — registry.
 *
 * Plaintext path (renderedDocument): sdk.write / sdk.read — content-addressed
 * PDF artifact catalog (public, non-PII).
 * E2E paths (faxTransmission / inboundFax): sdk.encryptedWrite /
 * sdk.encryptedRead — confidential message-metadata sealed in the kotoba
 * envelope (ADR-2605181100), read-cap = owner DID + explicit recipients. The
 * substrate never sees recipient/sender fax numbers in plaintext.
 *
 * Both E2E collections share the default wrapper collection, so every scan MUST
 * filter by innerType to keep the two partitions isolated.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  RENDERED_DOC_COLLECTION,
  TRANSMISSION_INNER_TYPE,
  INBOUND_INNER_TYPE,
  documentDidFor,
  documentRkey,
  transmissionRkey,
  inboundRkey,
  isHexBlobKey,
  isOptUint,
  isUint,
  type CoverageInput,
  type CoverageOutput,
  type FaxTransmissionBody,
  type FaxTransmissionView,
  type GetDocumentInput,
  type GetDocumentOutput,
  type GetTransmissionInput,
  type GetTransmissionOutput,
  type InboundFaxBody,
  type InboundFaxView,
  type ListDocumentsInput,
  type ListDocumentsOutput,
  type ListInboundInput,
  type ListInboundOutput,
  type ListTransmissionsInput,
  type ListTransmissionsOutput,
  type RecordInboundInput,
  type RecordInboundOutput,
  type RecordTransmissionInput,
  type RecordTransmissionOutput,
  type RegisterDocumentInput,
  type RegisterDocumentOutput,
  type RenderedDocumentRecord,
  type RenderedDocumentView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Rendered document (PLAINTEXT) ──────────────────────────────────

export async function registerDocument(e: Etzhayyim, input: RegisterDocumentInput): Promise<RegisterDocumentOutput> {
  if (!input.blobKey || !input.format) return { status: "rejected", error: "missingRequiredFields" };
  if (!isHexBlobKey(input.blobKey)) return { status: "rejected", error: "invalidBlobKey" };
  if (!isUint(input.pageCount)) return { status: "rejected", error: "invalidPageCount" };
  if (!isUint(input.byteSize)) return { status: "rejected", error: "invalidByteSize" };
  const rkey = documentRkey(input.blobKey);
  const existing = await e
    .read<RenderedDocumentRecord>({ collection: RENDERED_DOC_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", documentUri: existing.records[0].uri, did: existing.records[0].value.did, blobKey: input.blobKey };
  }
  const now = new Date().toISOString();
  const did = documentDidFor(input.blobKey);
  const record: RenderedDocumentRecord = {
    did,
    blobKey: input.blobKey,
    format: input.format,
    pageCount: input.pageCount,
    byteSize: input.byteSize,
    pageSize: input.pageSize ?? "A4",
    renderedAt: input.renderedAt ?? now,
    createdAt: now,
  };
  const receipt = await e.write({ collection: RENDERED_DOC_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", documentUri: receipt.uri, did, blobKey: input.blobKey };
}

export async function getDocument(e: Etzhayyim, input: GetDocumentInput): Promise<GetDocumentOutput> {
  if (!input.blobKey) return { error: "invalidBlobKey" };
  const resp = await e
    .read<RenderedDocumentRecord>({ collection: RENDERED_DOC_COLLECTION, rkey: documentRkey(input.blobKey) })
    .catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { document: { ...r.value, documentUri: r.uri } };
}

export async function listDocuments(e: Etzhayyim, input: ListDocumentsInput = {}): Promise<ListDocumentsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<RenderedDocumentRecord>({ collection: RENDERED_DOC_COLLECTION, cursor: input.cursor, limit });
  const items: RenderedDocumentView[] = resp.records
    .filter((r) => !input.format || r.value.format === input.format)
    .map((r) => ({ ...r.value, documentUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Fax transmission (E2E-ENCRYPTED) ───────────────────────────────

export async function recordTransmission(e: Etzhayyim, input: RecordTransmissionInput): Promise<RecordTransmissionOutput> {
  if (!input.txId || !input.to) return { status: "rejected", error: "missingRequiredFields" };
  if (!isOptUint(input.pageCount)) return { status: "rejected", error: "invalidPageCount" };
  const body: FaxTransmissionBody = {
    txId: input.txId,
    to: input.to,
    from: input.from,
    subject: input.subject,
    caseId: input.caseId,
    status: input.status ?? "queued",
    pageCount: input.pageCount,
    blobKey: input.blobKey,
    sentAt: input.sentAt,
    deliveredAt: input.deliveredAt,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: TRANSMISSION_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: transmissionRkey(input.txId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, txId: input.txId };
}

async function scanTransmissions(e: Etzhayyim, maxScan: number): Promise<FaxTransmissionView[]> {
  const out: FaxTransmissionView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<FaxTransmissionBody>({ innerType: TRANSMISSION_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listTransmissions(e: Etzhayyim, input: ListTransmissionsInput = {}): Promise<ListTransmissionsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanTransmissions(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter(
    (t) =>
      (!input.caseId || t.caseId === input.caseId) &&
      (!input.status || t.status === input.status) &&
      (!input.to || t.to === input.to),
  );
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getTransmission(e: Etzhayyim, input: GetTransmissionInput): Promise<GetTransmissionOutput> {
  if (!input.txId) return { error: "invalidTxId" };
  const all = await scanTransmissions(e, DEFAULT_MAX_SCAN);
  const found = all.find((t) => t.txId === input.txId);
  if (!found) return { error: "notFound" };
  return { transmission: found };
}

// ─── Inbound fax (E2E-ENCRYPTED) ────────────────────────────────────

export async function recordInbound(e: Etzhayyim, input: RecordInboundInput): Promise<RecordInboundOutput> {
  if (!input.rxId || !input.from) return { status: "rejected", error: "missingRequiredFields" };
  if (!isOptUint(input.pageCount)) return { status: "rejected", error: "invalidPageCount" };
  const body: InboundFaxBody = {
    rxId: input.rxId,
    from: input.from,
    to: input.to,
    pageCount: input.pageCount,
    blobKey: input.blobKey,
    receivedAt: input.receivedAt ?? new Date().toISOString(),
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: INBOUND_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: inboundRkey(input.rxId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, rxId: input.rxId };
}

async function scanInbound(e: Etzhayyim, maxScan: number): Promise<InboundFaxView[]> {
  const out: InboundFaxView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<InboundFaxBody>({ innerType: INBOUND_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listInbound(e: Etzhayyim, input: ListInboundInput = {}): Promise<ListInboundOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanInbound(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((r) => !input.from || r.from === input.from);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const transmissionsByStatus: Record<string, number> = {};
  let renderedDocumentCount = 0;
  let cursor: string | undefined;
  while (renderedDocumentCount < maxScan) {
    const page = await e.read<RenderedDocumentRecord>({ collection: RENDERED_DOC_COLLECTION, cursor, limit: PAGE_LIMIT });
    renderedDocumentCount += page.records.length;
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const transmissions = await scanTransmissions(e, maxScan);
  for (const t of transmissions) {
    transmissionsByStatus[t.status] = (transmissionsByStatus[t.status] ?? 0) + 1;
  }
  const inboundFaxCount = (await scanInbound(e, maxScan)).length;
  return {
    renderedDocumentCount,
    faxTransmissionCount: transmissions.length,
    inboundFaxCount,
    transmissionsByStatus,
    truncated:
      renderedDocumentCount >= maxScan || transmissions.length >= maxScan || inboundFaxCount >= maxScan,
  };
}
