/**
 * meeting-recorder kotoba — meeting minutes 議事録 generation.
 *
 * Closes the "minutes generation designed but not coded" gap left by the
 * 2026-04-22 session (90-docs/260422-meeting-recorder-session-summary.md):
 * transcriptSegment records → summary + decisions + action items + topics,
 * sealed as a meetingMinutes record in the kotoba E2E envelope
 * (ADR-2605181100, read-cap = owner DID + explicit recipients).
 *
 * Two generators:
 *   • extractive — deterministic, hermetic, stdlib-only. Always available;
 *     the canonical R0 path. Marker-based decision / action-item extraction
 *     (ja + en), keyword topics, lead+keyword summary.
 *   • murakumo — Murakumo LLM via LiteLLM loopback (G4 Murakumo-only,
 *     ADR-2605215000). Refused-by-default membrane, same shape as karakuri
 *     nl_plan: requires BOTH the caller's allowLive flag AND the operator
 *     gate env MEETING_RECORDER_LIVE_LLM=1. No silent fallback — a refused
 *     or failed live call is an honest rejection, never a quiet downgrade.
 *
 * The transcript text reaches this module only because the caller's sdk
 * identity can decrypt the segment envelopes; the substrate never sees
 * plaintext, and the minutes body is re-sealed the same way.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  MINUTES_INNER_TYPE,
  SEGMENT_INNER_TYPE,
  isUint,
  minutesRkey,
  type ActionItem,
  type GenerateMinutesInput,
  type GenerateMinutesOutput,
  type GetMinutesInput,
  type GetMinutesOutput,
  type ListMinutesInput,
  type ListMinutesOutput,
  type MeetingMinutesBody,
  type MeetingMinutesView,
  type TranscriptSegmentBody,
  type TranscriptSegmentView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SEGMENTS = 2000;
const MAX_SEGMENTS_CAP = 10_000;
const SUMMARY_SENTENCE_BUDGET = 5;
const SUMMARY_CHAR_CAP = 2000;
const TOPIC_BUDGET = 5;

// ── Murakumo membrane (G4 Murakumo-only, refused by default) ─────────

export const LIVE_LLM_GATE_ENV = "MEETING_RECORDER_LIVE_LLM";
const MURAKUMO_ENDPOINT_ENV = "MURAKUMO_ENDPOINT";
const DEFAULT_MURAKUMO_ENDPOINT = "http://127.0.0.1:4000/v1/chat/completions";
const DEFAULT_MURAKUMO_MODEL = "gemma3:4b";

type FetchLike = (url: string, init: { method: string; headers: Record<string, string>; body: string }) => Promise<{
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}>;

function liveGateOpen(env: Record<string, string | undefined> | undefined): boolean {
  return (env?.[LIVE_LLM_GATE_ENV] ?? "") === "1";
}

/** G4: the only inference path is the loopback LiteLLM Murakumo gateway. */
function murakumoEndpoint(env: Record<string, string | undefined> | undefined): string {
  const url = env?.[MURAKUMO_ENDPOINT_ENV] ?? DEFAULT_MURAKUMO_ENDPOINT;
  const host = new URL(url).hostname;
  if (host !== "127.0.0.1" && host !== "localhost" && host !== "::1") {
    throw new Error(`G4 violation: Murakumo endpoint must be loopback LiteLLM, got ${host}`);
  }
  return url;
}

// ── Sentence + marker extraction (ja + en) ───────────────────────────

interface Sentence {
  text: string;
  speakerHash?: string;
  order: number;
}

const DECISION_MARKERS = [
  /\b(?:decided|agreed|approved|resolved|finalized|sign(?:ed)? off)\b/i,
  /(?:決定|決まりました|決めました|合意|承認|採用します|採用しました|することにし(?:た|ます)|で行きましょう|で進めます|に確定)/,
];

const ACTION_MARKERS = [
  /\b(?:action item|to-?do|follow(?:\s|-)?up|will (?:do|send|prepare|draft|write|share|schedule|review|update|fix|set up)|needs? to|assigned to)\b/i,
  /(?:宿題|タスク|アクション|対応します|対応をお願いします|お願いします|してください|やっておきます|やります|担当します|までに|共有します|送ります|準備します|確認しておきます)/,
];

const ISO_DATE = /(\d{4}-\d{2}-\d{2})/;

const STOPWORDS = new Set([
  // en
  "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "is", "are",
  "was", "were", "be", "been", "this", "that", "these", "those", "it", "its", "we",
  "you", "they", "he", "she", "i", "my", "our", "your", "their", "with", "from",
  "as", "at", "by", "so", "if", "then", "than", "not", "no", "yes", "ok", "okay",
  "will", "would", "can", "could", "should", "do", "does", "did", "have", "has",
  "had", "about", "into", "just", "also", "very", "there", "here", "what", "when",
  "which", "who", "how", "all", "any", "some", "more", "let", "lets", "going",
  // ja (function-ish tokens that survive the kanji/katakana tokenizer)
  "こと", "もの", "ところ", "ため", "よう", "それ", "これ", "あれ", "どれ",
  "さん", "ちゃん", "そう", "はい", "いいえ", "です", "ます", "今日", "明日",
]);

function splitSentences(segments: TranscriptSegmentView[]): Sentence[] {
  const out: Sentence[] = [];
  let order = 0;
  for (const seg of segments) {
    for (const raw of seg.text.split(/(?<=[.!?。！？])\s*|\n+/)) {
      const text = raw.trim();
      if (text.length === 0) continue;
      out.push({ text, speakerHash: seg.speakerHash, order: order++ });
    }
  }
  return out;
}

function matchesAny(text: string, markers: RegExp[]): boolean {
  return markers.some((m) => m.test(text));
}

/** Tokens for topic/summary scoring: latin words ≥3 chars + kanji/katakana runs ≥2 chars. */
function tokenize(text: string): string[] {
  const tokens: string[] = [];
  for (const m of text.matchAll(/[A-Za-z][A-Za-z0-9_-]{2,}/g)) tokens.push(m[0].toLowerCase());
  for (const m of text.matchAll(/[一-鿿゠-ヿ]{2,}/g)) tokens.push(m[0]);
  return tokens.filter((t) => !STOPWORDS.has(t));
}

function topTopics(sentences: Sentence[]): { topics: string[]; freq: Map<string, number> } {
  const freq = new Map<string, number>();
  for (const s of sentences) for (const t of tokenize(s.text)) freq.set(t, (freq.get(t) ?? 0) + 1);
  const topics = [...freq.entries()]
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, TOPIC_BUDGET)
    .map(([t]) => t);
  return { topics, freq };
}

function extractDecisions(sentences: Sentence[]): string[] {
  return sentences.filter((s) => matchesAny(s.text, DECISION_MARKERS)).map((s) => s.text);
}

function extractActionItems(sentences: Sentence[]): ActionItem[] {
  return sentences
    .filter((s) => matchesAny(s.text, ACTION_MARKERS))
    .map((s) => {
      const item: ActionItem = { description: s.text };
      if (s.speakerHash) item.ownerHash = s.speakerHash;
      const due = s.text.match(ISO_DATE);
      if (due) item.dueDate = due[1];
      return item;
    });
}

/**
 * Lead + keyword-overlap extractive summary: the opening sentence anchors
 * context, then the highest keyword-scoring sentences follow in transcript
 * order. Deterministic for a given transcript.
 */
function extractSummary(sentences: Sentence[], freq: Map<string, number>): string {
  if (sentences.length === 0) return "";
  const scored = sentences.map((s) => ({
    s,
    score: tokenize(s.text).reduce((acc, t) => acc + (freq.get(t) ?? 0), 0),
  }));
  const picked = new Set<number>([0]);
  for (const { s } of [...scored].sort((a, b) => b.score - a.score || a.s.order - b.s.order)) {
    if (picked.size >= SUMMARY_SENTENCE_BUDGET) break;
    picked.add(s.order);
  }
  const summary = sentences
    .filter((s) => picked.has(s.order))
    .map((s) => s.text)
    .join(" ");
  return summary.length > SUMMARY_CHAR_CAP ? summary.slice(0, SUMMARY_CHAR_CAP) : summary;
}

function majorityLang(segments: TranscriptSegmentView[]): string | undefined {
  const counts = new Map<string, number>();
  for (const s of segments) if (s.lang) counts.set(s.lang, (counts.get(s.lang) ?? 0) + 1);
  let best: string | undefined;
  let bestN = 0;
  for (const [lang, n] of counts) if (n > bestN) { best = lang; bestN = n; }
  return best;
}

/** Deterministic hermetic generator — the canonical R0 path. */
export function extractiveMinutes(
  sessionId: string,
  segments: TranscriptSegmentView[],
  lang: string | undefined,
  generatedAt: string,
): MeetingMinutesBody {
  const sentences = splitSentences(segments);
  const { topics, freq } = topTopics(sentences);
  const participantHashes = [...new Set(segments.map((s) => s.speakerHash).filter((h): h is string => !!h))];
  return {
    sessionId,
    lang: lang ?? majorityLang(segments),
    summary: extractSummary(sentences, freq),
    decisions: extractDecisions(sentences),
    actionItems: extractActionItems(sentences),
    topics,
    participantHashes,
    generator: "extractive",
    sourceSegmentCount: segments.length,
    generatedAt,
  };
}

// ── Murakumo live path (gated) ───────────────────────────────────────

interface MurakumoShape {
  summary?: unknown;
  decisions?: unknown;
  actionItems?: unknown;
  topics?: unknown;
}

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function asActionItems(v: unknown): ActionItem[] {
  if (!Array.isArray(v)) return [];
  const out: ActionItem[] = [];
  for (const x of v) {
    if (typeof x !== "object" || x === null) continue;
    const r = x as Record<string, unknown>;
    if (typeof r.description !== "string" || r.description.length === 0) continue;
    const item: ActionItem = { description: r.description };
    if (typeof r.ownerHash === "string") item.ownerHash = r.ownerHash;
    if (typeof r.dueDate === "string" && ISO_DATE.test(r.dueDate)) item.dueDate = r.dueDate;
    out.push(item);
  }
  return out;
}

/**
 * Murakumo LLM minutes via LiteLLM loopback. Throws on transport / parse
 * failure — the caller surfaces an honest rejection, never a silent
 * downgrade to the extractive path.
 */
export async function murakumoMinutes(
  sessionId: string,
  segments: TranscriptSegmentView[],
  lang: string | undefined,
  generatedAt: string,
  opts: { env?: Record<string, string | undefined>; fetchFn?: FetchLike; model?: string } = {},
): Promise<MeetingMinutesBody> {
  const env = opts.env ?? (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  const endpoint = murakumoEndpoint(env);
  const model = opts.model ?? env?.MURAKUMO_MODEL ?? DEFAULT_MURAKUMO_MODEL;
  const fetchFn = opts.fetchFn ?? (globalThis.fetch as unknown as FetchLike);

  const outLang = lang ?? majorityLang(segments) ?? "ja";
  const transcript = segments
    .map((s) => `[${s.speakerHash ?? "unknown"}] ${s.text}`)
    .join("\n");

  const res = await fetchFn(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      temperature: 0,
      messages: [
        {
          role: "system",
          content:
            "You generate meeting minutes from a transcript. Reply with ONLY a JSON object: " +
            '{"summary": string, "decisions": string[], "actionItems": [{"description": string, "ownerHash"?: string, "dueDate"?: "YYYY-MM-DD"}], "topics": string[]}. ' +
            `Write summary/decisions/actionItems in language "${outLang}". ownerHash must be copied verbatim from the [bracketed] speaker tags, never invented.`,
        },
        { role: "user", content: transcript },
      ],
    }),
  });
  if (!res.ok) throw new Error(`murakumo chat/completions failed: ${res.status}`);
  const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
  const content = data.choices?.[0]?.message?.content ?? "";
  const stripped = content.replace(/^```(?:json)?\s*/i, "").replace(/\s*```\s*$/, "").trim();
  let shape: MurakumoShape;
  try {
    shape = JSON.parse(stripped) as MurakumoShape;
  } catch {
    throw new Error("murakumo returned non-JSON minutes payload");
  }
  if (typeof shape.summary !== "string" || shape.summary.length === 0) {
    throw new Error("murakumo minutes missing summary");
  }
  const participantHashes = [...new Set(segments.map((s) => s.speakerHash).filter((h): h is string => !!h))];
  return {
    sessionId,
    lang: outLang,
    summary: shape.summary.slice(0, SUMMARY_CHAR_CAP * 10),
    decisions: asStringArray(shape.decisions),
    actionItems: asActionItems(shape.actionItems),
    topics: asStringArray(shape.topics).slice(0, TOPIC_BUDGET * 2),
    participantHashes,
    generator: "murakumo",
    model,
    sourceSegmentCount: segments.length,
    generatedAt,
  };
}

// ── Segment scan (E2E read, session-filtered) ────────────────────────

async function scanSegmentsFor(e: Etzhayyim, sessionId: string, maxSegments: number): Promise<TranscriptSegmentView[]> {
  const out: TranscriptSegmentView[] = [];
  let cursor: string | undefined;
  while (out.length < maxSegments) {
    const page = await e.encryptedRead<TranscriptSegmentBody>({ innerType: SEGMENT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      if (r.value.sessionId === sessionId) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out.slice(0, maxSegments).sort((a, b) => a.seq - b.seq);
}

// ── Commands ─────────────────────────────────────────────────────────

export async function generateMinutes(
  e: Etzhayyim,
  input: GenerateMinutesInput,
  opts: { env?: Record<string, string | undefined>; fetchFn?: FetchLike } = {},
): Promise<GenerateMinutesOutput> {
  if (!input.sessionId) return { status: "rejected", error: "missingSessionId" };
  if (input.maxSegments !== undefined && (!isUint(input.maxSegments) || input.maxSegments === 0)) {
    return { status: "rejected", error: "invalidMaxSegments" };
  }
  const maxSegments = Math.min(input.maxSegments ?? DEFAULT_MAX_SEGMENTS, MAX_SEGMENTS_CAP);

  const segments = await scanSegmentsFor(e, input.sessionId, maxSegments);
  if (segments.length === 0) return { status: "rejected", error: "noSegments", sessionId: input.sessionId };

  const generatedAt = new Date().toISOString();
  let minutes: MeetingMinutesBody;
  if (input.allowLive) {
    const env = opts.env ?? (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
    if (!liveGateOpen(env)) {
      // Refused-by-default membrane (G4/G6 pattern): allowLive without the
      // operator gate is an honest rejection, never a silent fallback.
      return { status: "rejected", error: "liveLLMRefused", sessionId: input.sessionId };
    }
    try {
      minutes = await murakumoMinutes(input.sessionId, segments, input.lang, generatedAt, opts);
    } catch (err) {
      return { status: "rejected", error: `murakumoFailed: ${(err as Error).message}`, sessionId: input.sessionId };
    }
  } else {
    minutes = extractiveMinutes(input.sessionId, segments, input.lang, generatedAt);
  }

  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: MINUTES_INNER_TYPE,
    record: minutes as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: minutesRkey(input.sessionId),
  });
  return {
    status: "generated",
    uri: receipt.uri,
    keyId: receipt.keyId,
    sessionId: input.sessionId,
    generator: minutes.generator,
    minutes,
  };
}

async function scanMinutes(e: Etzhayyim, maxScan: number): Promise<MeetingMinutesView[]> {
  const out: MeetingMinutesView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<MeetingMinutesBody>({ innerType: MINUTES_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function getMinutes(e: Etzhayyim, input: GetMinutesInput): Promise<GetMinutesOutput> {
  if (!input.sessionId) return { error: "invalidSessionId" };
  const all = await scanMinutes(e, MAX_SEGMENTS_CAP);
  // Same-rkey regeneration appends a newer record in scan order; latest wins.
  const matches = all.filter((m) => m.sessionId === input.sessionId);
  const found = matches[matches.length - 1];
  if (!found) return { error: "notFound" };
  return { minutes: found };
}

export async function listMinutes(e: Etzhayyim, input: ListMinutesInput = {}): Promise<ListMinutesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanMinutes(e, MAX_SEGMENTS_CAP);
  const filtered = all.filter(
    (m) =>
      (!input.sessionId || m.sessionId === input.sessionId) &&
      (!input.generator || m.generator === input.generator),
  );
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function countMinutes(e: Etzhayyim, maxScan: number): Promise<number> {
  return (await scanMinutes(e, maxScan)).length;
}
