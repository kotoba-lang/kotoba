/**
 * site kotoba — registry.
 *
 * Plaintext path (topic / domain / page / wat): sdk.write / sdk.read — the open
 * web CATALOG. page → domain FK enforced via exists() (read + check), mirroring
 * air-cargo's uldAssignment → shipment FK.
 *
 * E2E path (followerEvent): sdk.encryptedWrite / sdk.encryptedRead — per-person
 * subscription/tracking activity sealed in the kotoba envelope (ADR-2605181100),
 * read-cap = owner DID + explicit recipients. The substrate never sees the
 * follower graph in plaintext.
 *
 * The 100B WET/screenshot crawl archive + crawl/embed/GPU inference are NOT
 * here — they stay etzhayyim (cannot fit AT PDS) and are consumed via
 * consent-capability.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  DOMAIN_COLLECTION,
  FOLLOWER_EVENT_INNER_TYPE,
  PAGE_COLLECTION,
  TOPIC_COLLECTION,
  WAT_COLLECTION,
  domainDidFor,
  domainRkey,
  followerEventRkey,
  isUint,
  pageDidFor,
  pageRkey,
  slugify,
  topicDidFor,
  topicRkey,
  watRkey,
  type CoverageInput,
  type CoverageOutput,
  type DomainRecord,
  type DomainView,
  type FollowerEventBody,
  type FollowerEventView,
  type GetDomainInput,
  type GetDomainOutput,
  type GetFollowerEventInput,
  type GetFollowerEventOutput,
  type GetPageInput,
  type GetPageOutput,
  type GetTopicInput,
  type GetTopicOutput,
  type ListDomainsInput,
  type ListDomainsOutput,
  type ListFollowerEventsInput,
  type ListFollowerEventsOutput,
  type ListPagesInput,
  type ListPagesOutput,
  type ListTopicsInput,
  type ListTopicsOutput,
  type ListWatInput,
  type ListWatOutput,
  type PageRecord,
  type PageView,
  type RecordFollowerEventInput,
  type RecordFollowerEventOutput,
  type RegisterDomainInput,
  type RegisterDomainOutput,
  type RegisterPageInput,
  type RegisterPageOutput,
  type RegisterTopicInput,
  type RegisterTopicOutput,
  type RegisterWatInput,
  type RegisterWatOutput,
  type TopicRecord,
  type TopicView,
  type WatRecord,
  type WatView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Plaintext FK helper (exists via read; mock has no exists()) ─────

async function domainExists(e: Etzhayyim, domain: string): Promise<boolean> {
  const rkey = domainRkey(domain);
  const resp = await e
    .read<DomainRecord>({ collection: DOMAIN_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: DomainRecord }> }));
  return Boolean(resp.records[0]?.value);
}

// ─── Topic coordinator (PLAINTEXT) ──────────────────────────────────

export async function registerTopic(e: Etzhayyim, input: RegisterTopicInput): Promise<RegisterTopicOutput> {
  if (!input.slug || !input.topic) return { status: "rejected", error: "missingRequiredFields" };
  const rkey = topicRkey(input.slug);
  const existing = await e.read<TopicRecord>({ collection: TOPIC_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", topicUri: existing.records[0].uri, did: existing.records[0].value.did, slug: input.slug };
  }
  const now = new Date().toISOString();
  const did = topicDidFor(input.slug);
  const record: TopicRecord = {
    did,
    slug: slugify(input.slug),
    topic: input.topic,
    category: input.category,
    createdAt: now,
  };
  const receipt = await e.write({ collection: TOPIC_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", topicUri: receipt.uri, did, slug: input.slug };
}

export async function getTopic(e: Etzhayyim, input: GetTopicInput): Promise<GetTopicOutput> {
  if (!input.slug) return { error: "invalidSlug" };
  const resp = await e.read<TopicRecord>({ collection: TOPIC_COLLECTION, rkey: topicRkey(input.slug) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { topic: { ...r.value, topicUri: r.uri } };
}

export async function listTopics(e: Etzhayyim, input: ListTopicsInput = {}): Promise<ListTopicsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<TopicRecord>({ collection: TOPIC_COLLECTION, cursor: input.cursor, limit });
  const items: TopicView[] = resp.records
    .filter((r) => !input.category || r.value.category === input.category)
    .map((r) => ({ ...r.value, topicUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Crawled domain (PLAINTEXT) ─────────────────────────────────────

export async function registerDomain(e: Etzhayyim, input: RegisterDomainInput): Promise<RegisterDomainOutput> {
  if (!input.domain) return { status: "rejected", error: "missingRequiredFields" };
  if (input.pageCount !== undefined && !isUint(input.pageCount)) return { status: "rejected", error: "invalidPageCount" };
  const rkey = domainRkey(input.domain);
  const existing = await e.read<DomainRecord>({ collection: DOMAIN_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", domainUri: existing.records[0].uri, did: existing.records[0].value.did, domain: input.domain };
  }
  const now = new Date().toISOString();
  const did = domainDidFor(input.domain);
  const record: DomainRecord = {
    did,
    domain: input.domain,
    slug: slugify(input.domain),
    tld: input.tld,
    pageCount: input.pageCount ?? 0,
    topics: input.topics ?? [],
    createdAt: now,
  };
  const receipt = await e.write({ collection: DOMAIN_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", domainUri: receipt.uri, did, domain: input.domain };
}

export async function getDomain(e: Etzhayyim, input: GetDomainInput): Promise<GetDomainOutput> {
  if (!input.domain) return { error: "invalidDomain" };
  const resp = await e.read<DomainRecord>({ collection: DOMAIN_COLLECTION, rkey: domainRkey(input.domain) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { domain: { ...r.value, domainUri: r.uri } };
}

export async function listDomains(e: Etzhayyim, input: ListDomainsInput = {}): Promise<ListDomainsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<DomainRecord>({ collection: DOMAIN_COLLECTION, cursor: input.cursor, limit });
  const items: DomainView[] = resp.records
    .filter((r) => !input.topic || r.value.topics.includes(input.topic))
    .map((r) => ({ ...r.value, domainUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Page metadata (PLAINTEXT, FK → domain) ─────────────────────────

export async function registerPage(e: Etzhayyim, input: RegisterPageInput): Promise<RegisterPageOutput> {
  if (!input.url || !input.domain) return { status: "rejected", error: "missingRequiredFields" };
  if (input.statusCode !== undefined && !isUint(input.statusCode)) return { status: "rejected", error: "invalidStatusCode" };
  if (!(await domainExists(e, input.domain))) return { status: "rejected", error: "unknownDomain" };
  const rkey = pageRkey(input.url);
  const existing = await e.read<PageRecord>({ collection: PAGE_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", pageUri: existing.records[0].uri, did: existing.records[0].value.did, url: input.url };
  }
  const now = new Date().toISOString();
  const did = pageDidFor(input.domain, input.url);
  const record: PageRecord = {
    did,
    url: input.url,
    domain: input.domain,
    title: input.title,
    contentHash: input.contentHash,
    language: input.language,
    statusCode: input.statusCode,
    topics: input.topics ?? [],
    createdAt: now,
  };
  const receipt = await e.write({ collection: PAGE_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", pageUri: receipt.uri, did, url: input.url };
}

export async function getPage(e: Etzhayyim, input: GetPageInput): Promise<GetPageOutput> {
  if (!input.url) return { error: "invalidUrl" };
  const resp = await e.read<PageRecord>({ collection: PAGE_COLLECTION, rkey: pageRkey(input.url) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { page: { ...r.value, pageUri: r.uri } };
}

export async function listPages(e: Etzhayyim, input: ListPagesInput = {}): Promise<ListPagesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<PageRecord>({ collection: PAGE_COLLECTION, cursor: input.cursor, limit });
  const items: PageView[] = resp.records
    .filter((r) => !input.domain || r.value.domain === input.domain)
    .map((r) => ({ ...r.value, pageUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── WAT link-graph metadata (PLAINTEXT) ────────────────────────────

export async function registerWat(e: Etzhayyim, input: RegisterWatInput): Promise<RegisterWatOutput> {
  if (!input.url || !input.domain) return { status: "rejected", error: "missingRequiredFields" };
  if (input.outlinkCount !== undefined && !isUint(input.outlinkCount)) return { status: "rejected", error: "invalidOutlinkCount" };
  if (input.statusCode !== undefined && !isUint(input.statusCode)) return { status: "rejected", error: "invalidStatusCode" };
  const rkey = watRkey(input.url);
  const existing = await e.read<WatRecord>({ collection: WAT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", watUri: existing.records[0].uri, did: existing.records[0].value.did, url: input.url };
  }
  const now = new Date().toISOString();
  const did = pageDidFor(input.domain, input.url);
  const record: WatRecord = {
    did,
    url: input.url,
    domain: input.domain,
    language: input.language,
    mimeType: input.mimeType,
    statusCode: input.statusCode,
    outlinkCount: input.outlinkCount ?? 0,
    createdAt: now,
  };
  const receipt = await e.write({ collection: WAT_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", watUri: receipt.uri, did, url: input.url };
}

export async function listWat(e: Etzhayyim, input: ListWatInput = {}): Promise<ListWatOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<WatRecord>({ collection: WAT_COLLECTION, cursor: input.cursor, limit });
  const items: WatView[] = resp.records
    .filter((r) => !input.domain || r.value.domain === input.domain)
    .map((r) => ({ ...r.value, watUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Follower event (E2E-ENCRYPTED, message-metadata) ───────────────

export async function recordFollowerEvent(e: Etzhayyim, input: RecordFollowerEventInput): Promise<RecordFollowerEventOutput> {
  if (!input.eventId || !input.followerDid || !input.topicSlug || !input.action) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const body: FollowerEventBody = {
    eventId: input.eventId,
    followerDid: input.followerDid,
    topicSlug: slugify(input.topicSlug),
    action: input.action,
    occurredAt: input.occurredAt ?? new Date().toISOString(),
  };
  // Read-cap = owner DID (sender, auto-wrapped) + any explicit recipients.
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: FOLLOWER_EVENT_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: followerEventRkey(input.eventId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, eventId: input.eventId };
}

async function scanFollowerEvents(e: Etzhayyim, maxScan: number): Promise<FollowerEventView[]> {
  const out: FollowerEventView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<FollowerEventBody>({ innerType: FOLLOWER_EVENT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listFollowerEvents(e: Etzhayyim, input: ListFollowerEventsInput = {}): Promise<ListFollowerEventsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanFollowerEvents(e, DEFAULT_MAX_SCAN);
  const topic = input.topicSlug ? slugify(input.topicSlug) : undefined;
  const filtered = all.filter((ev) => !topic || ev.topicSlug === topic);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getFollowerEvent(e: Etzhayyim, input: GetFollowerEventInput): Promise<GetFollowerEventOutput> {
  if (!input.eventId) return { error: "invalidEventId" };
  const all = await scanFollowerEvents(e, DEFAULT_MAX_SCAN);
  const found = all.find((ev) => ev.eventId === input.eventId);
  if (!found) return { error: "notFound" };
  return { event: found };
}

// ─── Coverage rollup (plaintext catalog + E2E countAll) ─────────────

async function countAll(e: Etzhayyim, collection: string, maxScan: number, onRecord?: (v: any) => void): Promise<number> {
  let total = 0;
  let cursor: string | undefined;
  while (total < maxScan) {
    const page = await e.read<any>({ collection, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      onRecord?.(r.value);
      total += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return total;
}

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const pagesByDomain: Record<string, number> = {};
  const topicCount = await countAll(e, TOPIC_COLLECTION, maxScan);
  const domainCount = await countAll(e, DOMAIN_COLLECTION, maxScan);
  const pageCount = await countAll(e, PAGE_COLLECTION, maxScan, (v) => {
    pagesByDomain[v.domain] = (pagesByDomain[v.domain] ?? 0) + 1;
  });
  const watCount = await countAll(e, WAT_COLLECTION, maxScan);
  const followerEventCount = (await scanFollowerEvents(e, maxScan)).length;
  return {
    topicCount,
    domainCount,
    pageCount,
    watCount,
    followerEventCount,
    pagesByDomain,
    truncated:
      topicCount >= maxScan ||
      domainCount >= maxScan ||
      pageCount >= maxScan ||
      watCount >= maxScan ||
      followerEventCount >= maxScan,
  };
}
