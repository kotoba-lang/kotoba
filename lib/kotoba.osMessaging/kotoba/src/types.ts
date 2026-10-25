/**
 * os-messaging kotoba — multi-platform messaging bridge, maximal migration.
 *
 * Per ADR-2606011400 (Consensys) + ADR-2605172400 (3-axis) + ADR-2605181100
 * (kotoba E2E encrypted-record envelope). Founder directive 2026-06-03: front
 * everything that can move; only the irreducible regulated EXECUTION stays etzhayyim.
 *
 * SPLIT (2 plaintext / 2 E2E):
 *   PLAINTEXT (public AT records) — the public crawl catalog:
 *     openChannel  : crawled public LINE/Telegram/etc channel directory
 *                    (title/description/country/language) — open metadata.
 *     scraperRun   : per-run operational aggregate stats
 *                    (status + messages-seen/new counts) — no subject content.
 *   E2E (kotoba envelope, read-cap = owner DID + recipients):
 *     bridge       : private control-plane — binds a private W-Protocol convo
 *                    (convoDid) + owner DID to a platform channel. This is
 *                    message-routing metadata, so it is sealed, not public.
 *     openMessage  : per-author scraped channel message (author label + text)
 *                    — private-content / message metadata, sealed E2E.
 *
 *   STAYS etzhayyim (consumed via consent-capability, NOT a collection) — the
 *   irreducible regulated EXECUTION: platform bot-token / secret custody, the
 *   actual webhook send/receive relay across the platform networks, and the
 *   crawl/scrape compute. The bridge/message/channel DATA all migrate; only the
 *   execution stays.
 *
 * FK demo: recordOpenMessage (E2E) verifies its parent openChannel (plaintext)
 * exists() before sealing — a cross-tier referential check.
 *
 * AT-Lexicon: no float — all counts are non-negative integers; no money fields.
 */

// ─── Collections / inner-types ──────────────────────────────────────
// Plaintext catalog collections.
export const OPEN_CHANNEL_COLLECTION = "com.etzhayyim.apps.osMessaging.openChannel";
export const SCRAPER_RUN_COLLECTION = "com.etzhayyim.apps.osMessaging.scraperRun";
// E2E inner-type NSIDs (body shape inside the encrypted envelope = collection NSID).
export const BRIDGE_INNER_TYPE = "com.etzhayyim.apps.osMessaging.bridge";
export const OPEN_MESSAGE_INNER_TYPE = "com.etzhayyim.apps.osMessaging.openMessage";

export const OSMSG_DID_PREFIX = "did:web:os-messaging.etzhayyim.com:" as const;

export type Platform =
  | "discord"
  | "telegram"
  | "slack"
  | "line"
  | "whatsapp"
  | "matrix"
  | "ms-teams"
  | "wechat"
  | "kakao";

export type BridgeMode = "read-only" | "read-write" | "agent-only" | "human-only" | "fully-bridged";
export type E2eMode = "client-signal" | "server-assisted" | "platform-native" | "plaintext";
export type RunStatus = "ok" | "partial" | "error";

// ─── openChannel (PLAINTEXT public crawl catalog) ───────────────────

export interface OpenChannelRecord {
  did: string;
  channelKey: string;
  platform: Platform;
  channelId: string;
  title: string;
  description?: string;
  country?: string;
  language?: string;
  channelUrl?: string;
  firstSeenAt: string;
  lastSeenAt: string;
  createdAt: string;
}
export interface OpenChannelView extends OpenChannelRecord {
  channelUri: string;
}
export interface RegisterChannelInput {
  channelKey: string;
  platform: Platform;
  channelId: string;
  title: string;
  description?: string;
  country?: string;
  language?: string;
  channelUrl?: string;
  firstSeenAt?: string;
  lastSeenAt?: string;
}
export interface RegisterChannelOutput {
  status: "recorded" | "alreadyExists" | "rejected";
  channelUri?: string;
  did?: string;
  channelKey?: string;
  error?: string;
}
export interface ListChannelsInput {
  platform?: Platform;
  country?: string;
  limit?: number;
  cursor?: string;
}
export interface ListChannelsOutput {
  items: OpenChannelView[];
  cursor?: string;
  total: number;
}
export interface GetChannelInput {
  channelKey: string;
}
export interface GetChannelOutput {
  channel?: OpenChannelView;
  error?: string;
}

// ─── scraperRun (PLAINTEXT operational aggregate) ───────────────────

export interface ScraperRunRecord {
  did: string;
  runId: string;
  platform: Platform;
  channelKey?: string;
  status: RunStatus;
  /** integer >= 0. */
  messagesSeen: number;
  /** integer >= 0. */
  messagesNew: number;
  startedAt: string;
  finishedAt?: string;
  errorMessage?: string;
  createdAt: string;
}
export interface ScraperRunView extends ScraperRunRecord {
  runUri: string;
}
export interface RecordRunInput {
  runId: string;
  platform: Platform;
  channelKey?: string;
  status: RunStatus;
  messagesSeen: number;
  messagesNew: number;
  startedAt?: string;
  finishedAt?: string;
  errorMessage?: string;
}
export interface RecordRunOutput {
  status: "recorded" | "alreadyExists" | "rejected";
  runUri?: string;
  did?: string;
  runId?: string;
  error?: string;
}
export interface ListRunsInput {
  platform?: Platform;
  status?: RunStatus;
  limit?: number;
  cursor?: string;
}
export interface ListRunsOutput {
  items: ScraperRunView[];
  cursor?: string;
  total: number;
}

// ─── bridge (E2E control-plane: convoDid + owner) ───────────────────

export interface BridgeBody {
  bridgeId: string;
  platform: Platform;
  channelId: string;
  channelName?: string;
  ownerDid: string;
  bridgeMode: BridgeMode;
  convoDid?: string;
  e2eMode: E2eMode;
  boundAt: string;
}
export interface BridgeView extends BridgeBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RegisterBridgeInput {
  bridgeId: string;
  platform: Platform;
  channelId: string;
  channelName?: string;
  ownerDid: string;
  bridgeMode: BridgeMode;
  convoDid?: string;
  e2eMode: E2eMode;
  boundAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RegisterBridgeOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  bridgeId?: string;
  error?: string;
}
export interface ListBridgesInput {
  platform?: Platform;
  bridgeMode?: BridgeMode;
  limit?: number;
  cursor?: string;
}
export interface ListBridgesOutput {
  items: BridgeView[];
  cursor?: string;
  total: number;
}
export interface GetBridgeInput {
  bridgeId: string;
}
export interface GetBridgeOutput {
  bridge?: BridgeView;
  error?: string;
}

// ─── openMessage (E2E per-author scraped content) ───────────────────

export interface OpenMessageBody {
  messageId: string;
  channelKey: string;
  platform: Platform;
  platformMessageId: string;
  authorLabel: string;
  messageText: string;
  messageUrl?: string;
  publishedAt?: string;
  observedAt: string;
}
export interface OpenMessageView extends OpenMessageBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordMessageInput {
  messageId: string;
  channelKey: string;
  platform: Platform;
  platformMessageId: string;
  authorLabel: string;
  messageText: string;
  messageUrl?: string;
  publishedAt?: string;
  observedAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RecordMessageOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  messageId?: string;
  error?: string;
}
export interface ListMessagesInput {
  channelKey?: string;
  platform?: Platform;
  limit?: number;
  cursor?: string;
}
export interface ListMessagesOutput {
  items: OpenMessageView[];
  cursor?: string;
  total: number;
}
export interface GetMessageInput {
  messageId: string;
}
export interface GetMessageOutput {
  message?: OpenMessageView;
  error?: string;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  openChannelCount?: number;
  scraperRunCount?: number;
  bridgeCount?: number;
  openMessageCount?: number;
  channelsByPlatform?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

const PLATFORMS: readonly Platform[] = [
  "discord", "telegram", "slack", "line", "whatsapp", "matrix", "ms-teams", "wechat", "kakao",
];
const BRIDGE_MODES: readonly BridgeMode[] = [
  "read-only", "read-write", "agent-only", "human-only", "fully-bridged",
];
const E2E_MODES: readonly E2eMode[] = [
  "client-signal", "server-assisted", "platform-native", "plaintext",
];
const RUN_STATUSES: readonly RunStatus[] = ["ok", "partial", "error"];

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isPlatform(v: unknown): v is Platform {
  return typeof v === "string" && PLATFORMS.includes(v as Platform);
}
export function isBridgeMode(v: unknown): v is BridgeMode {
  return typeof v === "string" && BRIDGE_MODES.includes(v as BridgeMode);
}
export function isE2eMode(v: unknown): v is E2eMode {
  return typeof v === "string" && E2E_MODES.includes(v as E2eMode);
}
export function isRunStatus(v: unknown): v is RunStatus {
  return typeof v === "string" && RUN_STATUSES.includes(v as RunStatus);
}
export function channelDidFor(id: string): string {
  return `${OSMSG_DID_PREFIX}ch:${id.toLowerCase()}`;
}
export function runDidFor(id: string): string {
  return `${OSMSG_DID_PREFIX}run:${id.toLowerCase()}`;
}
function slug(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
export function channelRkey(id: string): string {
  return `ch-${slug(id)}`;
}
export function runRkey(id: string): string {
  return `run-${slug(id)}`;
}
export function bridgeRkey(id: string): string {
  return `bridge-${slug(id)}`;
}
export function messageRkey(id: string): string {
  return `msg-${slug(id)}`;
}
