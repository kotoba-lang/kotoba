/**
 * meet kotoba — Google Meet + recorder migration (kotoba-E2E split).
 *
 * Per ADR-2606011400 (Consensys) + ADR-2605172400 (3-axis) + ADR-2605181100
 * (kotoba E2E encrypted-record envelope). Founder directive 2026-06-03: front
 * everything that can move; PII / private content migrate to etzhayyim when made
 * safe via kotoba E2E.
 *
 * SPLIT (maximal migration):
 *   PLAINTEXT (public AT records) —
 *     meeting          : scheduled-meeting catalog (title/status/scheduledAt,
 *                        provider, duration) = public ops facts.
 *     recordingChunk   : media-chunk POINTER metadata (seq/codec/key/sha/size/
 *                        duration) = catalog over the media archive. FK → meeting
 *                        via exists(). No per-person presence fields (PII Tier 1)
 *                        live here — those are in the E2E participant collection.
 *   E2E (kotoba envelope, com.etzhayyim.encrypted.record; read-cap = owner DID +
 *   explicit recipients) —
 *     recorderSession  : on-behalf-of identity + external-meeting linkage (PII).
 *     participant      : per-person presence + display name (PII Tier 1).
 *     transcriptSegment: spoken-content text (private content).
 *
 *   STAYS etzhayyim (consumed via consent-capability, NOT a collection) — the
 *   irreducible regulated EXECUTION: GPU/LLM (MLX whisper) transcription
 *   inference; recorder-bot join/leave enforcement ACTIONS; OAuth-token / consent
 *   credential custody; and the very-large media-byte archive (recording bytes
 *   physically cannot fit AT PDS — the pointer metadata above fronts plaintext).
 *
 * AT-Lexicon: no float — all counts/durations are integers; transcript
 * confidence is carried as integer percent 0-100 (confidencePct), not the
 * lexicon's 0-1 float.
 */

// Plaintext public collections.
export const MEETING_COLLECTION = "com.etzhayyim.apps.meet.meeting";
export const CHUNK_COLLECTION = "com.etzhayyim.apps.meet.recordingChunk";
// E2E inner-type NSIDs (body shape inside the encrypted envelope).
export const SESSION_INNER_TYPE = "com.etzhayyim.apps.meet.recorderSession";
export const PARTICIPANT_INNER_TYPE = "com.etzhayyim.apps.meet.participant";
export const TRANSCRIPT_INNER_TYPE = "com.etzhayyim.apps.meet.transcriptSegment";

export const MEET_DID_PREFIX = "did:web:meet.etzhayyim.com:" as const;

export type Provider = "teams" | "meet" | "zoom";
export type ChunkKind = "audio" | "video" | "mixed";

// ─── Meeting (PLAINTEXT, public catalog) ────────────────────────────

export interface MeetingRecord {
  did: string;
  meetingId: string;
  title: string;
  provider: Provider;
  status: string;
  scheduledAt?: string;
  durationSeconds?: number;
  createdAt: string;
}
export interface MeetingView extends MeetingRecord {
  meetingUri: string;
}
export interface RegisterMeetingInput {
  meetingId: string;
  title: string;
  provider: Provider;
  status?: string;
  scheduledAt?: string;
  durationSeconds?: number;
}
export interface RegisterMeetingOutput {
  status: "registered" | "alreadyExists" | "rejected";
  meetingUri?: string;
  did?: string;
  meetingId?: string;
  error?: string;
}
export interface GetMeetingInput {
  meetingId: string;
}
export interface GetMeetingOutput {
  meeting?: MeetingView;
  error?: string;
}
export interface ListMeetingsInput {
  provider?: Provider;
  status?: string;
  limit?: number;
  cursor?: string;
}
export interface ListMeetingsOutput {
  items: MeetingView[];
  cursor?: string;
  total: number;
}

// ─── Recording chunk (PLAINTEXT, pointer catalog, FK → meeting) ──────

export interface ChunkRecord {
  did: string;
  meetingId: string;
  provider: Provider;
  seq: number;
  kind: ChunkKind;
  codec?: string;
  archiveBucket?: string;
  archiveKey: string;
  sha256?: string;
  sizeBytes?: number;
  startedAt?: string;
  durationMs: number;
  createdAt: string;
}
export interface ChunkView extends ChunkRecord {
  chunkUri: string;
}
export interface RecordChunkInput {
  meetingId: string;
  provider: Provider;
  seq: number;
  kind: ChunkKind;
  archiveKey: string;
  codec?: string;
  archiveBucket?: string;
  sha256?: string;
  sizeBytes?: number;
  startedAt?: string;
  durationMs: number;
}
export interface RecordChunkOutput {
  status: "recorded" | "alreadyExists" | "rejected";
  chunkUri?: string;
  did?: string;
  error?: string;
}
export interface ListChunksInput {
  meetingId?: string;
  kind?: ChunkKind;
  limit?: number;
  cursor?: string;
}
export interface ListChunksOutput {
  items: ChunkView[];
  cursor?: string;
  total: number;
}

// ─── Recorder session (E2E-ENCRYPTED, PII) ──────────────────────────

export interface RecorderSessionBody {
  sessionId: string;
  meetingId: string;
  provider: Provider;
  onBehalfOfDid: string;
  externalMeetingId?: string;
  status: string;
  durationMs?: number;
  startedAt?: string;
  endedAt?: string;
}
export interface RecorderSessionView extends RecorderSessionBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface OpenSessionInput {
  sessionId: string;
  meetingId: string;
  provider: Provider;
  onBehalfOfDid: string;
  externalMeetingId?: string;
  status?: string;
  durationMs?: number;
  startedAt?: string;
  endedAt?: string;
  recipients?: string[];
}
export interface OpenSessionOutput {
  status: "opened" | "rejected";
  uri?: string;
  keyId?: string;
  sessionId?: string;
  error?: string;
}
export interface ListSessionsInput {
  provider?: Provider;
  status?: string;
  limit?: number;
}
export interface ListSessionsOutput {
  items: RecorderSessionView[];
  total: number;
}
export interface GetSessionInput {
  sessionId: string;
}
export interface GetSessionOutput {
  session?: RecorderSessionView;
  error?: string;
}

// ─── Participant (E2E-ENCRYPTED, PII Tier 1) ────────────────────────

export interface ParticipantBody {
  sessionId: string;
  providerIdHash: string;
  displayName?: string;
  participantDid?: string;
  role?: string;
  joinedAt?: string;
  leftAt?: string;
  speakingMs?: number;
}
export interface ParticipantView extends ParticipantBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface AddParticipantInput {
  sessionId: string;
  providerIdHash: string;
  displayName?: string;
  participantDid?: string;
  role?: string;
  joinedAt?: string;
  leftAt?: string;
  speakingMs?: number;
  recipients?: string[];
}
export interface AddParticipantOutput {
  status: "added" | "rejected";
  uri?: string;
  keyId?: string;
  error?: string;
}
export interface ListParticipantsInput {
  sessionId?: string;
  limit?: number;
}
export interface ListParticipantsOutput {
  items: ParticipantView[];
  total: number;
}

// ─── Transcript segment (E2E-ENCRYPTED, private content) ────────────

export interface TranscriptSegmentBody {
  sessionId: string;
  chunkSeq?: number;
  seq: number;
  startedAtMs: number;
  endedAtMs: number;
  speakerHash?: string;
  lang?: string;
  /** integer percent 0-100 (lexicon's 0-1 float remapped). */
  confidencePct?: number;
  text: string;
  model?: string;
}
export interface TranscriptSegmentView extends TranscriptSegmentBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface AddSegmentInput {
  sessionId: string;
  seq: number;
  startedAtMs: number;
  endedAtMs: number;
  text: string;
  chunkSeq?: number;
  speakerHash?: string;
  lang?: string;
  confidencePct?: number;
  model?: string;
  recipients?: string[];
}
export interface AddSegmentOutput {
  status: "added" | "rejected";
  uri?: string;
  keyId?: string;
  error?: string;
}
export interface ListSegmentsInput {
  sessionId?: string;
  limit?: number;
}
export interface ListSegmentsOutput {
  items: TranscriptSegmentView[];
  total: number;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  meetingCount?: number;
  recordingChunkCount?: number;
  recorderSessionCount?: number;
  participantCount?: number;
  transcriptSegmentCount?: number;
  meetingsByProvider?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isPct(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 100;
}
export function meetingDidFor(id: string): string {
  return `${MEET_DID_PREFIX}mtg:${id.toLowerCase()}`;
}
export function chunkDidFor(meetingId: string, seq: number): string {
  return `${MEET_DID_PREFIX}chunk:${meetingId.toLowerCase()}:${seq}`;
}
export function rkeyOf(prefix: string, id: string): string {
  return `${prefix}-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
