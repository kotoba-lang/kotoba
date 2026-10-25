/**
 * meeting-recorder kotoba — WAVE 2 maximal migration (kotoba-E2E split).
 *
 * Per ADR-2606011400 (Consensys product-front / infra-back) + ADR-2605172400
 * (3-axis OR-test) + ADR-2605181100 (kotoba E2E encrypted-record envelope).
 * Founder directive 2026-06-03: front everything that can move; only the
 * irreducible regulated EXECUTION stays etzhayyim.
 *
 * SPLIT:
 *   PUBLIC (plaintext AT records) — provider capability catalog: which meeting
 *   providers (teams/meet/zoom) the recorder supports, their codec + chunking
 *   limits. PII-free open reference metadata; safe on-substrate plaintext.
 *
 *   SENSITIVE (kotoba E2E, com.etzhayyim.encrypted.record) — three per-person
 *   record kinds, each sealed via sdk.encryptedWrite (read-cap = owner DID +
 *   explicit recipients):
 *     • session       — onBehalfOfDid + externalMeetingId + status/timeline
 *                        (per-person, consent-gated in the lexicon).
 *     • recordingChunk — B2 blob POINTER metadata + participantHashes (PII Tier
 *                        1). The media blob itself stays etzhayyim (large archive).
 *     • transcriptSegment — speaker + transcript text. The envelope IS the
 *                        encryption; text travels as a plain field.
 *   All three land in the default wrapper collection, so every scan filters by
 *   its own innerType (= the collection NSID) to avoid cross-contamination.
 *
 *   STAYS etzhayyim (consumed via consent-capability) — NOT a collection:
 *     • recorder-bot JOIN / CAPTURE execution (dispatching the bot into a
 *       teams/meet/zoom call, capturing A/V) — enforcement/action.
 *     • GPU/MLX whisper-large-v3 transcription INFERENCE.
 *     • B2 media-blob custody (very-large media archive that cannot fit AT PDS).
 *     • consentToken / credential / raw-key custody.
 *
 * AT-Lexicon: no float. The lexicon's confidence (0-1 float) is migrated to an
 * integer confidencePct (0-100). All other numerics (durationMs, *AtMs,
 * sizeBytes, seq, chunkSeconds) are already integers.
 */

// Plaintext public collection.
export const PROVIDER_CATALOG_COLLECTION = "com.etzhayyim.apps.meetingRecorder.providerCapability";
// E2E inner-type NSIDs (= the collection NSID for each sealed body shape).
export const SESSION_INNER_TYPE = "com.etzhayyim.apps.meetingRecorder.session";
export const CHUNK_INNER_TYPE = "com.etzhayyim.apps.meetingRecorder.recordingChunk";
export const SEGMENT_INNER_TYPE = "com.etzhayyim.apps.meetingRecorder.transcriptSegment";
export const MINUTES_INNER_TYPE = "com.etzhayyim.apps.meetingRecorder.meetingMinutes";

export const MR_DID_PREFIX = "did:web:meeting-recorder.etzhayyim.com:" as const;

export type Provider = "teams" | "meet" | "zoom";
export type SessionStatus = "joining" | "joined" | "left" | "failed" | "rejected";
export type ChunkKind = "audio" | "video" | "mixed";

// ─── Provider capability (PLAINTEXT, public reference catalog) ───────

export interface ProviderCapabilityRecord {
  did: string;
  provider: Provider;
  displayName: string;
  codecs: string[];
  minChunkSeconds: number;
  maxChunkSeconds: number;
  supportsVideo: boolean;
  supportsTranscription: boolean;
  createdAt: string;
}
export interface ProviderCapabilityView extends ProviderCapabilityRecord {
  capabilityUri: string;
}
export interface RegisterProviderInput {
  provider: Provider;
  displayName: string;
  codecs: string[];
  minChunkSeconds: number;
  maxChunkSeconds: number;
  supportsVideo?: boolean;
  supportsTranscription?: boolean;
}
export interface RegisterProviderOutput {
  status: "registered" | "alreadyExists" | "rejected";
  capabilityUri?: string;
  did?: string;
  provider?: Provider;
  error?: string;
}
export interface GetProviderInput {
  provider: Provider;
}
export interface GetProviderOutput {
  provider?: ProviderCapabilityView;
  error?: string;
}
export interface ListProvidersInput {
  supportsVideo?: boolean;
  limit?: number;
  cursor?: string;
}
export interface ListProvidersOutput {
  items: ProviderCapabilityView[];
  cursor?: string;
  total: number;
}

// ─── Session (E2E-ENCRYPTED, per-person consent-gated) ──────────────

export interface SessionBody {
  sessionId: string;
  provider: Provider;
  onBehalfOfDid: string;
  externalMeetingId?: string;
  status: SessionStatus;
  startedAt: string;
  endedAt?: string;
  durationMs?: number;
  chunkCount: number;
  participantCount: number;
}
export interface SessionView extends SessionBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordSessionInput {
  sessionId: string;
  provider: Provider;
  onBehalfOfDid: string;
  externalMeetingId?: string;
  status: SessionStatus;
  startedAt?: string;
  endedAt?: string;
  durationMs?: number;
  chunkCount?: number;
  participantCount?: number;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RecordSessionOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  sessionId?: string;
  error?: string;
}
export interface GetSessionInput {
  sessionId: string;
}
export interface GetSessionOutput {
  session?: SessionView;
  error?: string;
}
export interface ListSessionsInput {
  provider?: Provider;
  status?: SessionStatus;
  onBehalfOfDid?: string;
  limit?: number;
  cursor?: string;
}
export interface ListSessionsOutput {
  items: SessionView[];
  cursor?: string;
  total: number;
}

// ─── Recording chunk (E2E-ENCRYPTED, B2 pointer + PII Tier 1) ────────

export interface RecordingChunkBody {
  sessionId: string;
  provider: Provider;
  seq: number;
  kind: ChunkKind;
  codec?: string;
  b2Bucket?: string;
  b2Key: string;
  sha256: string;
  sizeBytes?: number;
  startedAt: string;
  durationMs: number;
  participantHashes: string[];
}
export interface RecordingChunkView extends RecordingChunkBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordChunkInput {
  sessionId: string;
  provider: Provider;
  seq: number;
  kind: ChunkKind;
  codec?: string;
  b2Bucket?: string;
  b2Key: string;
  sha256: string;
  sizeBytes?: number;
  startedAt?: string;
  durationMs: number;
  participantHashes?: string[];
  recipients?: string[];
}
export interface RecordChunkOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  error?: string;
}
export interface ListChunksInput {
  sessionId?: string;
  limit?: number;
  cursor?: string;
}
export interface ListChunksOutput {
  items: RecordingChunkView[];
  cursor?: string;
  total: number;
}

// ─── Transcript segment (E2E-ENCRYPTED, transcript content) ──────────

export interface TranscriptSegmentBody {
  sessionId: string;
  chunkSeq: number;
  seq: number;
  startedAtMs: number;
  endedAtMs: number;
  speakerHash?: string;
  lang?: string;
  /** integer 0-100 (migrated from the lexicon's 0-1 float). */
  confidencePct: number;
  /** Transcript text. The kotoba envelope is the encryption; plain field here. */
  text: string;
  model?: string;
}
export interface TranscriptSegmentView extends TranscriptSegmentBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordSegmentInput {
  sessionId: string;
  chunkSeq: number;
  seq: number;
  startedAtMs: number;
  endedAtMs: number;
  speakerHash?: string;
  lang?: string;
  confidencePct: number;
  text: string;
  model?: string;
  recipients?: string[];
}
export interface RecordSegmentOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  error?: string;
}
export interface ListSegmentsInput {
  sessionId?: string;
  limit?: number;
  cursor?: string;
}
export interface ListSegmentsOutput {
  items: TranscriptSegmentView[];
  cursor?: string;
  total: number;
}

// ─── Meeting minutes 議事録 (E2E-ENCRYPTED, generated from segments) ──

export type MinutesGenerator = "extractive" | "murakumo";

export interface ActionItem {
  description: string;
  /** speakerHash of the participant the item is attributed to. */
  ownerHash?: string;
  /** ISO-8601 date (YYYY-MM-DD) when one was stated in the meeting. */
  dueDate?: string;
}

export interface MeetingMinutesBody {
  sessionId: string;
  lang?: string;
  summary: string;
  decisions: string[];
  actionItems: ActionItem[];
  topics: string[];
  participantHashes: string[];
  generator: MinutesGenerator;
  /** Set when generator=murakumo (e.g. gemma3:4b). */
  model?: string;
  sourceSegmentCount: number;
  generatedAt: string;
}
export interface MeetingMinutesView extends MeetingMinutesBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface GenerateMinutesInput {
  sessionId: string;
  lang?: string;
  /**
   * Request the Murakumo LLM path. Honored only when the operator gate
   * (MEETING_RECORDER_LIVE_LLM=1) is also on; otherwise the call is refused
   * (no silent fallback) — same membrane as karakuri nl_plan (G4/G6).
   */
  allowLive?: boolean;
  maxSegments?: number;
  recipients?: string[];
}
export interface GenerateMinutesOutput {
  status: "generated" | "rejected";
  uri?: string;
  keyId?: string;
  sessionId?: string;
  generator?: MinutesGenerator;
  minutes?: MeetingMinutesBody;
  error?: string;
}
export interface GetMinutesInput {
  sessionId: string;
}
export interface GetMinutesOutput {
  minutes?: MeetingMinutesView;
  error?: string;
}
export interface ListMinutesInput {
  sessionId?: string;
  generator?: MinutesGenerator;
  limit?: number;
  cursor?: string;
}
export interface ListMinutesOutput {
  items: MeetingMinutesView[];
  cursor?: string;
  total: number;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  providerCapabilityCount?: number;
  sessionCount?: number;
  recordingChunkCount?: number;
  transcriptSegmentCount?: number;
  meetingMinutesCount?: number;
  sessionsByProvider?: Record<string, number>;
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
export function providerDidFor(p: string): string {
  return `${MR_DID_PREFIX}prov:${p.toLowerCase()}`;
}
export function providerRkey(p: string): string {
  return `prov-${p.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function sessionRkey(id: string): string {
  return `sess-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
export function chunkRkey(sessionId: string, seq: number): string {
  return `chunk-${sessionId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${seq}`;
}
export function segmentRkey(sessionId: string, seq: number): string {
  return `seg-${sessionId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${seq}`;
}
export function minutesRkey(sessionId: string): string {
  return `minutes-${sessionId.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
