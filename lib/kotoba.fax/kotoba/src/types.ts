/**
 * fax kotoba — kotoba-E2E split for the FAX correspondence app.
 *
 * Per ADR-2606011400 (Consensys product-front / infra-back) + ADR-2605172400
 * (3-axis OR-test) + ADR-2605181100 (kotoba E2E encrypted-record envelope).
 * Founder directive 2026-06-03: MAXIMAL migration — front everything that can
 * move; only the irreducible regulated EXECUTION stays etzhayyim.
 *
 * SPLIT:
 *   PUBLIC (plaintext AT records) — renderedDocument: content-addressed PDF
 *   artifact metadata (blobKey = SHA-256 of bytes, format, pageCount, byteSize,
 *   pageSize, renderedAt). No recipient, no case content — frontable open
 *   document-catalog metadata via sdk.write / sdk.read.
 *
 *   SENSITIVE (kotoba E2E, com.etzhayyim.encrypted.record) — per-correspondence
 *   message-metadata sealed via sdk.encryptedWrite (read-cap = owner DID +
 *   explicit recipients):
 *     - faxTransmission: outbound send / manual-handoff record. Recipient fax
 *       number (E.164 PII) + caseId + subject tie to legal/compliance matters
 *       (労基署 / 裁判所 / 内容証明). Confidential message-metadata.
 *     - inboundFax: received fax. Sender fax number (PII) + artifact pointer.
 *   Both share the default wrapper collection, partitioned by innerType.
 *
 *   STAYS etzhayyim (consumed via consent-capability, NOT a collection) — the
 *   irreducible regulated EXECUTION: the provider transmission CALL (Phaxio /
 *   Dropbox Fax UI handoff), provider-API credential custody, content-addressed
 *   blob-byte custody (CDN), and headless PDF render compute. The transmission
 *   DATA migrates as E2E records; the send/render/custody ACTS stay etzhayyim.
 *
 * AT-Lexicon: no float — pageCount / byteSize are integers. No money fields.
 */

// Plaintext public collection.
export const RENDERED_DOC_COLLECTION = "com.etzhayyim.apps.fax.renderedDocument";
// E2E inner-type NSIDs (body shape inside each encrypted envelope).
export const TRANSMISSION_INNER_TYPE = "com.etzhayyim.apps.fax.faxTransmission";
export const INBOUND_INNER_TYPE = "com.etzhayyim.apps.fax.inboundFax";

export const FAX_DID_PREFIX = "did:web:fax.etzhayyim.com:" as const;

export type FaxStatus = "queued" | "sending" | "success" | "failure" | "needs_human" | "unknown";
export type DocFormat = "text" | "markdown" | "html";
export type PageSize = "A4" | "Letter" | "Legal";

// ─── Rendered document (PLAINTEXT, public artifact catalog) ──────────

export interface RenderedDocumentRecord {
  did: string;
  /** Content-address: SHA-256 hex of the rendered PDF bytes. */
  blobKey: string;
  format: DocFormat;
  pageCount: number;
  byteSize: number;
  pageSize: PageSize;
  renderedAt: string;
  createdAt: string;
}
export interface RenderedDocumentView extends RenderedDocumentRecord {
  documentUri: string;
}
export interface RegisterDocumentInput {
  blobKey: string;
  format: DocFormat;
  pageCount: number;
  byteSize: number;
  pageSize?: PageSize;
  renderedAt?: string;
}
export interface RegisterDocumentOutput {
  status: "registered" | "alreadyExists" | "rejected";
  documentUri?: string;
  did?: string;
  blobKey?: string;
  error?: string;
}
export interface GetDocumentInput {
  blobKey: string;
}
export interface GetDocumentOutput {
  document?: RenderedDocumentView;
  error?: string;
}
export interface ListDocumentsInput {
  format?: DocFormat;
  limit?: number;
  cursor?: string;
}
export interface ListDocumentsOutput {
  items: RenderedDocumentView[];
  cursor?: string;
  total: number;
}

// ─── Fax transmission (E2E-ENCRYPTED, confidential message-metadata) ─

export interface FaxTransmissionBody {
  txId: string;
  /** Recipient fax number (E.164 PII). */
  to: string;
  from?: string;
  subject?: string;
  /** Related business/legal case id (e.g. matsuoka-2504). */
  caseId?: string;
  status: FaxStatus;
  pageCount?: number;
  /** Content-address of the sent artifact (FK → renderedDocument.blobKey). */
  blobKey?: string;
  sentAt?: string;
  deliveredAt?: string;
}
export interface FaxTransmissionView extends FaxTransmissionBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordTransmissionInput {
  txId: string;
  to: string;
  from?: string;
  subject?: string;
  caseId?: string;
  status?: FaxStatus;
  pageCount?: number;
  blobKey?: string;
  sentAt?: string;
  deliveredAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RecordTransmissionOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  txId?: string;
  error?: string;
}
export interface ListTransmissionsInput {
  caseId?: string;
  status?: FaxStatus;
  to?: string;
  limit?: number;
}
export interface ListTransmissionsOutput {
  items: FaxTransmissionView[];
  total: number;
}
export interface GetTransmissionInput {
  txId: string;
}
export interface GetTransmissionOutput {
  transmission?: FaxTransmissionView;
  error?: string;
}

// ─── Inbound fax (E2E-ENCRYPTED, confidential message-metadata) ──────

export interface InboundFaxBody {
  rxId: string;
  /** Sender fax number (PII). */
  from: string;
  to?: string;
  pageCount?: number;
  /** Content-address of the received PDF artifact. */
  blobKey?: string;
  receivedAt: string;
}
export interface InboundFaxView extends InboundFaxBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordInboundInput {
  rxId: string;
  from: string;
  to?: string;
  pageCount?: number;
  blobKey?: string;
  receivedAt?: string;
  recipients?: string[];
}
export interface RecordInboundOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  rxId?: string;
  error?: string;
}
export interface ListInboundInput {
  from?: string;
  limit?: number;
}
export interface ListInboundOutput {
  items: InboundFaxView[];
  total: number;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  renderedDocumentCount?: number;
  faxTransmissionCount?: number;
  inboundFaxCount?: number;
  transmissionsByStatus?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isOptUint(n: unknown): boolean {
  return n === undefined || isUint(n);
}
export function isHexBlobKey(s: unknown): s is string {
  return typeof s === "string" && /^[0-9a-f]{8,128}$/.test(s);
}
export function documentDidFor(blobKey: string): string {
  return `${FAX_DID_PREFIX}doc:${blobKey.toLowerCase()}`;
}
export function documentRkey(blobKey: string): string {
  return `doc-${blobKey.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function transmissionRkey(txId: string): string {
  return `tx-${txId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function inboundRkey(rxId: string): string {
  return `rx-${rxId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
