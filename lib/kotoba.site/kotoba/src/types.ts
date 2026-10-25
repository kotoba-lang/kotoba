/**
 * site kotoba — Internet Clone Gateway, kotoba product front.
 *
 * Per ADR-2606011400 (Consensys product-front / infra-back) + ADR-2605172400
 * (3-axis split) + ADR-2605181100 (kotoba E2E encrypted-record envelope).
 * Founder directive 2026-06-03: MAXIMAL migration — front the page/domain/topic
 * CATALOG metadata plaintext; front per-person follower-subscription activity
 * E2E; only the irreducible regulated EXECUTION + the physically-too-large
 * archive stay etzhayyim.
 *
 * SPLIT:
 *   PLAINTEXT (public AT records, sdk.write/read) — the catalog: topic
 *   coordinators, crawled domains, page metadata (url/title/contentHash/topics)
 *   and WAT link-graph metadata (outlinks/status/language). These are open web
 *   facts; frontable. page → domain FK via exists().
 *
 *   E2E (kotoba envelope, com.etzhayyim.encrypted.record) — followerEvent:
 *   per-person subscription/tracking activity (which DID follows which topic).
 *   "Who is tracking what" is message-metadata, never public — sealed via
 *   sdk.encryptedWrite, read-cap = owner DID + explicit recipients.
 *
 *   STAYS etzhayyim (consumed via consent-capability, NOT a collection) — the
 *   100B-page WET/screenshot crawl archive (physically cannot fit AT PDS) + the
 *   crawl / embed / screenshot pipeline + Murakumo GPU embedding INFERENCE. The
 *   catalog metadata above fronts plaintext; the bulk content + compute stay
 *   etzhayyim-resident.
 *
 * AT-Lexicon: no float (counts/depths/codes are integers; quality/priority are
 * integer 0-100). No money fields here.
 */

// ─── Plaintext collections ──────────────────────────────────────────
export const TOPIC_COLLECTION = "com.etzhayyim.apps.site.topic";
export const DOMAIN_COLLECTION = "com.etzhayyim.apps.site.domain";
export const PAGE_COLLECTION = "com.etzhayyim.apps.site.page";
export const WAT_COLLECTION = "com.etzhayyim.apps.site.wat";
// E2E inner-type NSID (body shape inside the encrypted envelope).
export const FOLLOWER_EVENT_INNER_TYPE = "com.etzhayyim.apps.site.followerEvent";

export const SITE_DID_PREFIX = "did:web:site.etzhayyim.com:" as const;

// ─── Topic coordinator (PLAINTEXT) ──────────────────────────────────

export interface TopicRecord {
  did: string;
  slug: string;
  topic: string;
  category?: string;
  createdAt: string;
}
export interface TopicView extends TopicRecord {
  topicUri: string;
}
export interface RegisterTopicInput {
  slug: string;
  topic: string;
  category?: string;
}
export interface RegisterTopicOutput {
  status: "registered" | "alreadyExists" | "rejected";
  topicUri?: string;
  did?: string;
  slug?: string;
  error?: string;
}
export interface GetTopicInput {
  slug: string;
}
export interface GetTopicOutput {
  topic?: TopicView;
  error?: string;
}
export interface ListTopicsInput {
  category?: string;
  limit?: number;
  cursor?: string;
}
export interface ListTopicsOutput {
  items: TopicView[];
  cursor?: string;
  total: number;
}

// ─── Crawled domain (PLAINTEXT) ─────────────────────────────────────

export interface DomainRecord {
  did: string;
  domain: string;
  slug: string;
  tld?: string;
  pageCount: number;
  topics: string[];
  createdAt: string;
}
export interface DomainView extends DomainRecord {
  domainUri: string;
}
export interface RegisterDomainInput {
  domain: string;
  tld?: string;
  pageCount?: number;
  topics?: string[];
}
export interface RegisterDomainOutput {
  status: "registered" | "alreadyExists" | "rejected";
  domainUri?: string;
  did?: string;
  domain?: string;
  error?: string;
}
export interface GetDomainInput {
  domain: string;
}
export interface GetDomainOutput {
  domain?: DomainView;
  error?: string;
}
export interface ListDomainsInput {
  topic?: string;
  limit?: number;
  cursor?: string;
}
export interface ListDomainsOutput {
  items: DomainView[];
  cursor?: string;
  total: number;
}

// ─── Page metadata (PLAINTEXT, FK → domain) ─────────────────────────

export interface PageRecord {
  did: string;
  url: string;
  domain: string;
  title?: string;
  contentHash?: string;
  language?: string;
  statusCode?: number;
  topics: string[];
  createdAt: string;
}
export interface PageView extends PageRecord {
  pageUri: string;
}
export interface RegisterPageInput {
  url: string;
  domain: string;
  title?: string;
  contentHash?: string;
  language?: string;
  statusCode?: number;
  topics?: string[];
}
export interface RegisterPageOutput {
  status: "registered" | "alreadyExists" | "rejected";
  pageUri?: string;
  did?: string;
  url?: string;
  error?: string;
}
export interface GetPageInput {
  url: string;
}
export interface GetPageOutput {
  page?: PageView;
  error?: string;
}
export interface ListPagesInput {
  domain?: string;
  limit?: number;
  cursor?: string;
}
export interface ListPagesOutput {
  items: PageView[];
  cursor?: string;
  total: number;
}

// ─── WAT link-graph metadata (PLAINTEXT) ────────────────────────────

export interface WatRecord {
  did: string;
  url: string;
  domain: string;
  language?: string;
  mimeType?: string;
  statusCode?: number;
  outlinkCount: number;
  createdAt: string;
}
export interface WatView extends WatRecord {
  watUri: string;
}
export interface RegisterWatInput {
  url: string;
  domain: string;
  language?: string;
  mimeType?: string;
  statusCode?: number;
  outlinkCount?: number;
}
export interface RegisterWatOutput {
  status: "registered" | "alreadyExists" | "rejected";
  watUri?: string;
  did?: string;
  url?: string;
  error?: string;
}
export interface ListWatInput {
  domain?: string;
  limit?: number;
  cursor?: string;
}
export interface ListWatOutput {
  items: WatView[];
  cursor?: string;
  total: number;
}

// ─── Follower event (E2E-ENCRYPTED, message-metadata) ───────────────

export interface FollowerEventBody {
  eventId: string;
  followerDid: string;
  topicSlug: string;
  /** "follow" | "unfollow" | "mention". */
  action: string;
  occurredAt: string;
}
export interface FollowerEventView extends FollowerEventBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordFollowerEventInput {
  eventId: string;
  followerDid: string;
  topicSlug: string;
  action: string;
  occurredAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RecordFollowerEventOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  eventId?: string;
  error?: string;
}
export interface ListFollowerEventsInput {
  topicSlug?: string;
  limit?: number;
  cursor?: string;
}
export interface ListFollowerEventsOutput {
  items: FollowerEventView[];
  cursor?: string;
  total: number;
}
export interface GetFollowerEventInput {
  eventId: string;
}
export interface GetFollowerEventOutput {
  event?: FollowerEventView;
  error?: string;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  topicCount?: number;
  domainCount?: number;
  pageCount?: number;
  watCount?: number;
  followerEventCount?: number;
  pagesByDomain?: Record<string, number>;
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
export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
export function topicDidFor(slug: string): string {
  return `${SITE_DID_PREFIX}topic:${slugify(slug)}`;
}
export function domainDidFor(domain: string): string {
  return `${SITE_DID_PREFIX}${slugify(domain)}`;
}
export function pageDidFor(domain: string, url: string): string {
  return `${SITE_DID_PREFIX}${slugify(domain)}:${slugify(url)}`;
}
export function topicRkey(slug: string): string {
  return `topic-${slugify(slug)}`;
}
export function domainRkey(domain: string): string {
  return `domain-${slugify(domain)}`;
}
export function pageRkey(url: string): string {
  return `page-${slugify(url)}`;
}
export function watRkey(url: string): string {
  return `wat-${slugify(url)}`;
}
export function followerEventRkey(id: string): string {
  return `fev-${slugify(id)}`;
}
