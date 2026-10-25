/**
 * meeting-recorder kotoba — WAVE 2 registry.
 *
 * Plaintext path (providerCapability): sdk.write / sdk.read — public reference
 * catalog of supported meeting providers.
 * E2E paths (session / recordingChunk / transcriptSegment): sdk.encryptedWrite /
 * sdk.encryptedRead — per-person bodies sealed in the kotoba envelope
 * (ADR-2605181100), read-cap = owner DID + explicit recipients. The substrate
 * never sees onBehalfOfDid / participant hashes / transcript text in plaintext.
 *
 * Three E2E inner-types share the default wrapper collection, so EVERY scan
 * passes its own innerType to keep counts/filters isolated.
 *
 * STAYS etzhayyim (consent-capability): recorder-bot join/capture execution, GPU/MLX
 * whisper inference, B2 media-blob custody, consentToken/credential custody.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import { countMinutes } from "./minutes.js";
import {
  CHUNK_INNER_TYPE,
  PROVIDER_CATALOG_COLLECTION,
  SEGMENT_INNER_TYPE,
  SESSION_INNER_TYPE,
  chunkRkey,
  isPct,
  isUint,
  providerDidFor,
  providerRkey,
  segmentRkey,
  sessionRkey,
  type CoverageInput,
  type CoverageOutput,
  type GetProviderInput,
  type GetProviderOutput,
  type GetSessionInput,
  type GetSessionOutput,
  type ListChunksInput,
  type ListChunksOutput,
  type ListProvidersInput,
  type ListProvidersOutput,
  type ListSegmentsInput,
  type ListSegmentsOutput,
  type ListSessionsInput,
  type ListSessionsOutput,
  type ProviderCapabilityRecord,
  type ProviderCapabilityView,
  type RecordChunkInput,
  type RecordChunkOutput,
  type RecordSegmentInput,
  type RecordSegmentOutput,
  type RecordSessionInput,
  type RecordSessionOutput,
  type RecordingChunkBody,
  type RecordingChunkView,
  type RegisterProviderInput,
  type RegisterProviderOutput,
  type SessionBody,
  type SessionView,
  type TranscriptSegmentBody,
  type TranscriptSegmentView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;
const VALID_PROVIDERS: ReadonlySet<string> = new Set(["teams", "meet", "zoom"]);
const VALID_CHUNK_KINDS: ReadonlySet<string> = new Set(["audio", "video", "mixed"]);

// ─── Provider capability (PLAINTEXT) ────────────────────────────────

export async function registerProvider(e: Etzhayyim, input: RegisterProviderInput): Promise<RegisterProviderOutput> {
  if (!input.provider || !VALID_PROVIDERS.has(input.provider)) return { status: "rejected", error: "invalidProvider" };
  if (!input.displayName) return { status: "rejected", error: "missingDisplayName" };
  if (!isUint(input.minChunkSeconds) || !isUint(input.maxChunkSeconds) || input.minChunkSeconds > input.maxChunkSeconds) {
    return { status: "rejected", error: "invalidChunkBounds" };
  }
  const rkey = providerRkey(input.provider);
  const existing = await e.read<ProviderCapabilityRecord>({ collection: PROVIDER_CATALOG_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", capabilityUri: existing.records[0].uri, did: existing.records[0].value.did, provider: input.provider };
  }
  const now = new Date().toISOString();
  const did = providerDidFor(input.provider);
  const record: ProviderCapabilityRecord = {
    did,
    provider: input.provider,
    displayName: input.displayName,
    codecs: input.codecs ?? [],
    minChunkSeconds: input.minChunkSeconds,
    maxChunkSeconds: input.maxChunkSeconds,
    supportsVideo: input.supportsVideo ?? false,
    supportsTranscription: input.supportsTranscription ?? false,
    createdAt: now,
  };
  const receipt = await e.write({ collection: PROVIDER_CATALOG_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", capabilityUri: receipt.uri, did, provider: input.provider };
}

export async function getProvider(e: Etzhayyim, input: GetProviderInput): Promise<GetProviderOutput> {
  if (!input.provider) return { error: "invalidProvider" };
  const resp = await e.read<ProviderCapabilityRecord>({ collection: PROVIDER_CATALOG_COLLECTION, rkey: providerRkey(input.provider) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { provider: { ...r.value, capabilityUri: r.uri } };
}

export async function listProviders(e: Etzhayyim, input: ListProvidersInput = {}): Promise<ListProvidersOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ProviderCapabilityRecord>({ collection: PROVIDER_CATALOG_COLLECTION, cursor: input.cursor, limit });
  const items: ProviderCapabilityView[] = resp.records
    .filter((r) => input.supportsVideo === undefined || r.value.supportsVideo === input.supportsVideo)
    .map((r) => ({ ...r.value, capabilityUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Session (E2E-ENCRYPTED) ────────────────────────────────────────

export async function recordSession(e: Etzhayyim, input: RecordSessionInput): Promise<RecordSessionOutput> {
  if (!input.sessionId || !input.onBehalfOfDid) return { status: "rejected", error: "missingRequiredFields" };
  if (!input.provider || !VALID_PROVIDERS.has(input.provider)) return { status: "rejected", error: "invalidProvider" };
  if (input.durationMs !== undefined && !isUint(input.durationMs)) return { status: "rejected", error: "invalidDurationMs" };
  const body: SessionBody = {
    sessionId: input.sessionId,
    provider: input.provider,
    onBehalfOfDid: input.onBehalfOfDid,
    externalMeetingId: input.externalMeetingId,
    status: input.status,
    startedAt: input.startedAt ?? new Date().toISOString(),
    endedAt: input.endedAt,
    durationMs: input.durationMs,
    chunkCount: input.chunkCount ?? 0,
    participantCount: input.participantCount ?? 0,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: SESSION_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: sessionRkey(input.sessionId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, sessionId: input.sessionId };
}

async function scanSessions(e: Etzhayyim, maxScan: number): Promise<SessionView[]> {
  const out: SessionView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<SessionBody>({ innerType: SESSION_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listSessions(e: Etzhayyim, input: ListSessionsInput = {}): Promise<ListSessionsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanSessions(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter(
    (s) =>
      (!input.provider || s.provider === input.provider) &&
      (!input.status || s.status === input.status) &&
      (!input.onBehalfOfDid || s.onBehalfOfDid === input.onBehalfOfDid),
  );
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getSession(e: Etzhayyim, input: GetSessionInput): Promise<GetSessionOutput> {
  if (!input.sessionId) return { error: "invalidSessionId" };
  const all = await scanSessions(e, DEFAULT_MAX_SCAN);
  const found = all.find((s) => s.sessionId === input.sessionId);
  if (!found) return { error: "notFound" };
  return { session: found };
}

// ─── Recording chunk (E2E-ENCRYPTED) ────────────────────────────────

export async function recordChunk(e: Etzhayyim, input: RecordChunkInput): Promise<RecordChunkOutput> {
  if (!input.sessionId || !input.b2Key || !input.sha256) return { status: "rejected", error: "missingRequiredFields" };
  if (!input.provider || !VALID_PROVIDERS.has(input.provider)) return { status: "rejected", error: "invalidProvider" };
  if (!input.kind || !VALID_CHUNK_KINDS.has(input.kind)) return { status: "rejected", error: "invalidKind" };
  if (!isUint(input.seq)) return { status: "rejected", error: "invalidSeq" };
  if (!isUint(input.durationMs)) return { status: "rejected", error: "invalidDurationMs" };
  if (input.sizeBytes !== undefined && !isUint(input.sizeBytes)) return { status: "rejected", error: "invalidSizeBytes" };
  const body: RecordingChunkBody = {
    sessionId: input.sessionId,
    provider: input.provider,
    seq: input.seq,
    kind: input.kind,
    codec: input.codec,
    b2Bucket: input.b2Bucket,
    b2Key: input.b2Key,
    sha256: input.sha256,
    sizeBytes: input.sizeBytes,
    startedAt: input.startedAt ?? new Date().toISOString(),
    durationMs: input.durationMs,
    participantHashes: input.participantHashes ?? [],
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: CHUNK_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: chunkRkey(input.sessionId, input.seq),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId };
}

async function scanChunks(e: Etzhayyim, maxScan: number): Promise<RecordingChunkView[]> {
  const out: RecordingChunkView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<RecordingChunkBody>({ innerType: CHUNK_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listChunks(e: Etzhayyim, input: ListChunksInput = {}): Promise<ListChunksOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanChunks(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((c) => !input.sessionId || c.sessionId === input.sessionId);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Transcript segment (E2E-ENCRYPTED) ─────────────────────────────

export async function recordSegment(e: Etzhayyim, input: RecordSegmentInput): Promise<RecordSegmentOutput> {
  if (!input.sessionId || input.text === undefined) return { status: "rejected", error: "missingRequiredFields" };
  if (!isUint(input.seq) || !isUint(input.chunkSeq)) return { status: "rejected", error: "invalidSeq" };
  if (!isUint(input.startedAtMs) || !isUint(input.endedAtMs)) return { status: "rejected", error: "invalidTimestamps" };
  if (!isPct(input.confidencePct)) return { status: "rejected", error: "invalidConfidencePct" };
  const body: TranscriptSegmentBody = {
    sessionId: input.sessionId,
    chunkSeq: input.chunkSeq,
    seq: input.seq,
    startedAtMs: input.startedAtMs,
    endedAtMs: input.endedAtMs,
    speakerHash: input.speakerHash,
    lang: input.lang,
    confidencePct: input.confidencePct,
    text: input.text,
    model: input.model,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: SEGMENT_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: segmentRkey(input.sessionId, input.seq),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId };
}

async function scanSegments(e: Etzhayyim, maxScan: number): Promise<TranscriptSegmentView[]> {
  const out: TranscriptSegmentView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<TranscriptSegmentBody>({ innerType: SEGMENT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listSegments(e: Etzhayyim, input: ListSegmentsInput = {}): Promise<ListSegmentsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanSegments(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((s) => !input.sessionId || s.sessionId === input.sessionId);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const sessionsByProvider: Record<string, number> = {};
  let providerCapabilityCount = 0;
  let cursor: string | undefined;
  while (providerCapabilityCount < maxScan) {
    const page = await e.read<ProviderCapabilityRecord>({ collection: PROVIDER_CATALOG_COLLECTION, cursor, limit: PAGE_LIMIT });
    providerCapabilityCount += page.records.length;
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const sessions = await scanSessions(e, maxScan);
  for (const s of sessions) sessionsByProvider[s.provider] = (sessionsByProvider[s.provider] ?? 0) + 1;
  const sessionCount = sessions.length;
  const recordingChunkCount = (await scanChunks(e, maxScan)).length;
  const transcriptSegmentCount = (await scanSegments(e, maxScan)).length;
  const meetingMinutesCount = await countMinutes(e, maxScan);
  return {
    providerCapabilityCount,
    sessionCount,
    recordingChunkCount,
    transcriptSegmentCount,
    meetingMinutesCount,
    sessionsByProvider,
    truncated:
      providerCapabilityCount >= maxScan ||
      sessionCount >= maxScan ||
      recordingChunkCount >= maxScan ||
      transcriptSegmentCount >= maxScan ||
      meetingMinutesCount >= maxScan,
  };
}
