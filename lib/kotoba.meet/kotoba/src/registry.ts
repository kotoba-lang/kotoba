/**
 * meet kotoba — kotoba-E2E registry.
 *
 * Plaintext path (meeting, recordingChunk): sdk.write / sdk.read — public
 * meeting catalog + media-chunk pointer metadata. FK recordingChunk → meeting
 * via exists() (read + check).
 * E2E path (recorderSession, participant, transcriptSegment): sdk.encryptedWrite
 * / sdk.encryptedRead — PII + private content sealed in the kotoba envelope
 * (ADR-2605181100), read-cap = owner DID + explicit recipients. The substrate
 * never sees on-behalf-of identity, participant presence, or spoken text in
 * plaintext.
 *
 * STAYS etzhayyim (consent-capability, not modeled as a collection) — MLX whisper
 * transcription inference, recorder-bot join/leave enforcement, OAuth/consent
 * credential custody, and the large media-byte archive.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  CHUNK_COLLECTION,
  MEETING_COLLECTION,
  PARTICIPANT_INNER_TYPE,
  SESSION_INNER_TYPE,
  TRANSCRIPT_INNER_TYPE,
  chunkDidFor,
  isPct,
  isUint,
  meetingDidFor,
  rkeyOf,
  type AddParticipantInput,
  type AddParticipantOutput,
  type AddSegmentInput,
  type AddSegmentOutput,
  type ChunkRecord,
  type ChunkView,
  type CoverageInput,
  type CoverageOutput,
  type GetMeetingInput,
  type GetMeetingOutput,
  type GetSessionInput,
  type GetSessionOutput,
  type ListChunksInput,
  type ListChunksOutput,
  type ListMeetingsInput,
  type ListMeetingsOutput,
  type ListParticipantsInput,
  type ListParticipantsOutput,
  type ListSegmentsInput,
  type ListSegmentsOutput,
  type ListSessionsInput,
  type ListSessionsOutput,
  type MeetingRecord,
  type MeetingView,
  type OpenSessionInput,
  type OpenSessionOutput,
  type ParticipantBody,
  type ParticipantView,
  type RecordChunkInput,
  type RecordChunkOutput,
  type RecorderSessionBody,
  type RecorderSessionView,
  type RegisterMeetingInput,
  type RegisterMeetingOutput,
  type TranscriptSegmentBody,
  type TranscriptSegmentView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Plaintext FK helper (exists via read; mock has no exists()) ─────

async function meetingExists(e: Etzhayyim, meetingId: string): Promise<boolean> {
  const rkey = rkeyOf("mtg", meetingId);
  const resp = await e
    .read<MeetingRecord>({ collection: MEETING_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: MeetingRecord }> }));
  return Boolean(resp.records[0]?.value);
}

// ─── Meeting (PLAINTEXT, public catalog) ────────────────────────────

export async function registerMeeting(e: Etzhayyim, input: RegisterMeetingInput): Promise<RegisterMeetingOutput> {
  if (!input.meetingId || !input.title || !input.provider) return { status: "rejected", error: "missingRequiredFields" };
  if (input.durationSeconds !== undefined && !isUint(input.durationSeconds)) return { status: "rejected", error: "invalidDurationSeconds" };
  const rkey = rkeyOf("mtg", input.meetingId);
  const existing = await e.read<MeetingRecord>({ collection: MEETING_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", meetingUri: existing.records[0].uri, did: existing.records[0].value.did, meetingId: input.meetingId };
  }
  const now = new Date().toISOString();
  const did = meetingDidFor(input.meetingId);
  const record: MeetingRecord = {
    did,
    meetingId: input.meetingId,
    title: input.title,
    provider: input.provider,
    status: input.status ?? "scheduled",
    scheduledAt: input.scheduledAt,
    durationSeconds: input.durationSeconds,
    createdAt: now,
  };
  const receipt = await e.write({ collection: MEETING_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", meetingUri: receipt.uri, did, meetingId: input.meetingId };
}

export async function getMeeting(e: Etzhayyim, input: GetMeetingInput): Promise<GetMeetingOutput> {
  if (!input.meetingId) return { error: "invalidMeetingId" };
  const rkey = rkeyOf("mtg", input.meetingId);
  const resp = await e.read<MeetingRecord>({ collection: MEETING_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { meeting: { ...r.value, meetingUri: r.uri } };
}

export async function listMeetings(e: Etzhayyim, input: ListMeetingsInput = {}): Promise<ListMeetingsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<MeetingRecord>({ collection: MEETING_COLLECTION, cursor: input.cursor, limit });
  const items: MeetingView[] = resp.records
    .filter((r) => (!input.provider || r.value.provider === input.provider) && (!input.status || r.value.status === input.status))
    .map((r) => ({ ...r.value, meetingUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Recording chunk (PLAINTEXT, pointer catalog, FK → meeting) ─────

export async function recordChunk(e: Etzhayyim, input: RecordChunkInput): Promise<RecordChunkOutput> {
  if (!input.meetingId || !input.archiveKey || !input.kind || !input.provider) return { status: "rejected", error: "missingRequiredFields" };
  if (!isUint(input.seq)) return { status: "rejected", error: "invalidSeq" };
  if (!isUint(input.durationMs)) return { status: "rejected", error: "invalidDurationMs" };
  if (input.sizeBytes !== undefined && !isUint(input.sizeBytes)) return { status: "rejected", error: "invalidSizeBytes" };
  if (!(await meetingExists(e, input.meetingId))) return { status: "rejected", error: "meetingNotFound" };
  const rkey = rkeyOf("chunk", `${input.meetingId}-${input.seq}`);
  const existing = await e.read<ChunkRecord>({ collection: CHUNK_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", chunkUri: existing.records[0].uri, did: existing.records[0].value.did };
  }
  const now = new Date().toISOString();
  const did = chunkDidFor(input.meetingId, input.seq);
  const record: ChunkRecord = {
    did,
    meetingId: input.meetingId,
    provider: input.provider,
    seq: input.seq,
    kind: input.kind,
    codec: input.codec,
    archiveBucket: input.archiveBucket,
    archiveKey: input.archiveKey,
    sha256: input.sha256,
    sizeBytes: input.sizeBytes,
    startedAt: input.startedAt,
    durationMs: input.durationMs,
    createdAt: now,
  };
  const receipt = await e.write({ collection: CHUNK_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "recorded", chunkUri: receipt.uri, did };
}

export async function listChunks(e: Etzhayyim, input: ListChunksInput = {}): Promise<ListChunksOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ChunkRecord>({ collection: CHUNK_COLLECTION, cursor: input.cursor, limit });
  const items: ChunkView[] = resp.records
    .filter((r) => (!input.meetingId || r.value.meetingId === input.meetingId) && (!input.kind || r.value.kind === input.kind))
    .map((r) => ({ ...r.value, chunkUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Recorder session (E2E-ENCRYPTED, PII) ──────────────────────────

export async function openSession(e: Etzhayyim, input: OpenSessionInput): Promise<OpenSessionOutput> {
  if (!input.sessionId || !input.meetingId || !input.provider || !input.onBehalfOfDid) return { status: "rejected", error: "missingRequiredFields" };
  if (input.durationMs !== undefined && !isUint(input.durationMs)) return { status: "rejected", error: "invalidDurationMs" };
  const body: RecorderSessionBody = {
    sessionId: input.sessionId,
    meetingId: input.meetingId,
    provider: input.provider,
    onBehalfOfDid: input.onBehalfOfDid,
    externalMeetingId: input.externalMeetingId,
    status: input.status ?? "joining",
    durationMs: input.durationMs,
    startedAt: input.startedAt,
    endedAt: input.endedAt,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: SESSION_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("sess", input.sessionId),
  });
  return { status: "opened", uri: receipt.uri, keyId: receipt.keyId, sessionId: input.sessionId };
}

async function scanSessions(e: Etzhayyim, maxScan: number): Promise<RecorderSessionView[]> {
  const out: RecorderSessionView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<RecorderSessionBody>({ innerType: SESSION_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listSessions(e: Etzhayyim, input: ListSessionsInput = {}): Promise<ListSessionsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanSessions(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((s) => (!input.provider || s.provider === input.provider) && (!input.status || s.status === input.status));
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getSession(e: Etzhayyim, input: GetSessionInput): Promise<GetSessionOutput> {
  if (!input.sessionId) return { error: "invalidSessionId" };
  const all = await scanSessions(e, DEFAULT_MAX_SCAN);
  const found = all.find((s) => s.sessionId === input.sessionId);
  if (!found) return { error: "notFound" };
  return { session: found };
}

// ─── Participant (E2E-ENCRYPTED, PII Tier 1) ────────────────────────

export async function addParticipant(e: Etzhayyim, input: AddParticipantInput): Promise<AddParticipantOutput> {
  if (!input.sessionId || !input.providerIdHash) return { status: "rejected", error: "missingRequiredFields" };
  if (input.speakingMs !== undefined && !isUint(input.speakingMs)) return { status: "rejected", error: "invalidSpeakingMs" };
  const body: ParticipantBody = {
    sessionId: input.sessionId,
    providerIdHash: input.providerIdHash,
    displayName: input.displayName,
    participantDid: input.participantDid,
    role: input.role,
    joinedAt: input.joinedAt,
    leftAt: input.leftAt,
    speakingMs: input.speakingMs,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: PARTICIPANT_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("part", `${input.sessionId}-${input.providerIdHash}`),
  });
  return { status: "added", uri: receipt.uri, keyId: receipt.keyId };
}

async function scanParticipants(e: Etzhayyim, maxScan: number): Promise<ParticipantView[]> {
  const out: ParticipantView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<ParticipantBody>({ innerType: PARTICIPANT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listParticipants(e: Etzhayyim, input: ListParticipantsInput = {}): Promise<ListParticipantsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanParticipants(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((p) => !input.sessionId || p.sessionId === input.sessionId);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

// ─── Transcript segment (E2E-ENCRYPTED, private content) ────────────

export async function addSegment(e: Etzhayyim, input: AddSegmentInput): Promise<AddSegmentOutput> {
  if (!input.sessionId || !input.text) return { status: "rejected", error: "missingRequiredFields" };
  if (!isUint(input.seq)) return { status: "rejected", error: "invalidSeq" };
  if (!isUint(input.startedAtMs) || !isUint(input.endedAtMs)) return { status: "rejected", error: "invalidTimestamps" };
  if (input.confidencePct !== undefined && !isPct(input.confidencePct)) return { status: "rejected", error: "invalidConfidencePct" };
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
    innerType: TRANSCRIPT_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("seg", `${input.sessionId}-${input.seq}`),
  });
  return { status: "added", uri: receipt.uri, keyId: receipt.keyId };
}

async function scanSegments(e: Etzhayyim, maxScan: number): Promise<TranscriptSegmentView[]> {
  const out: TranscriptSegmentView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<TranscriptSegmentBody>({ innerType: TRANSCRIPT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
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

async function countCollection<T>(e: Etzhayyim, collection: string, maxScan: number): Promise<number> {
  let count = 0;
  let cursor: string | undefined;
  while (count < maxScan) {
    const page = await e.read<T>({ collection, cursor, limit: PAGE_LIMIT });
    count += page.records.length;
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return count;
}

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const meetingsByProvider: Record<string, number> = {};
  let meetingCount = 0;
  let cursor: string | undefined;
  while (meetingCount < maxScan) {
    const page = await e.read<MeetingRecord>({ collection: MEETING_COLLECTION, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      meetingsByProvider[r.value.provider] = (meetingsByProvider[r.value.provider] ?? 0) + 1;
      meetingCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const recordingChunkCount = await countCollection<ChunkRecord>(e, CHUNK_COLLECTION, maxScan);
  const recorderSessionCount = (await scanSessions(e, maxScan)).length;
  const participantCount = (await scanParticipants(e, maxScan)).length;
  const transcriptSegmentCount = (await scanSegments(e, maxScan)).length;
  return {
    meetingCount,
    recordingChunkCount,
    recorderSessionCount,
    participantCount,
    transcriptSegmentCount,
    meetingsByProvider,
    truncated:
      meetingCount >= maxScan ||
      recordingChunkCount >= maxScan ||
      recorderSessionCount >= maxScan ||
      participantCount >= maxScan ||
      transcriptSegmentCount >= maxScan,
  };
}
