/**
 * os-messaging kotoba — registry.
 *
 * Plaintext path (openChannel, scraperRun): sdk.write / sdk.read — the public
 * crawl catalog + operational aggregates.
 * E2E path (bridge, openMessage): sdk.encryptedWrite / sdk.encryptedRead —
 * private routing control-plane + per-author scraped content sealed in the
 * kotoba envelope (ADR-2605181100), read-cap = owner DID + recipients. The
 * substrate never sees convo bindings or message text in plaintext.
 *
 * Cross-tier FK: recordOpenMessage (E2E) checks its parent openChannel
 * (plaintext) exists() before sealing.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  BRIDGE_INNER_TYPE,
  OPEN_CHANNEL_COLLECTION,
  OPEN_MESSAGE_INNER_TYPE,
  SCRAPER_RUN_COLLECTION,
  bridgeRkey,
  channelDidFor,
  channelRkey,
  isBridgeMode,
  isE2eMode,
  isPlatform,
  isRunStatus,
  isUint,
  messageRkey,
  runDidFor,
  runRkey,
  type BridgeBody,
  type BridgeView,
  type CoverageInput,
  type CoverageOutput,
  type GetBridgeInput,
  type GetBridgeOutput,
  type GetChannelInput,
  type GetChannelOutput,
  type GetMessageInput,
  type GetMessageOutput,
  type ListBridgesInput,
  type ListBridgesOutput,
  type ListChannelsInput,
  type ListChannelsOutput,
  type ListMessagesInput,
  type ListMessagesOutput,
  type ListRunsInput,
  type ListRunsOutput,
  type OpenChannelRecord,
  type OpenChannelView,
  type OpenMessageBody,
  type OpenMessageView,
  type RecordMessageInput,
  type RecordMessageOutput,
  type RecordRunInput,
  type RecordRunOutput,
  type RegisterBridgeInput,
  type RegisterBridgeOutput,
  type RegisterChannelInput,
  type RegisterChannelOutput,
  type ScraperRunRecord,
  type ScraperRunView,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── openChannel (PLAINTEXT public crawl catalog) ───────────────────

async function channelExists(e: Etzhayyim, channelKey: string): Promise<boolean> {
  const rkey = channelRkey(channelKey);
  const existing = await e
    .read<OpenChannelRecord>({ collection: OPEN_CHANNEL_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: OpenChannelRecord }> }));
  return Boolean(existing.records[0]?.value);
}

export async function registerChannel(e: Etzhayyim, input: RegisterChannelInput): Promise<RegisterChannelOutput> {
  if (!input.channelKey || !input.channelId || !input.title) return { status: "rejected", error: "missingRequiredFields" };
  if (!isPlatform(input.platform)) return { status: "rejected", error: "invalidPlatform" };
  const rkey = channelRkey(input.channelKey);
  const existing = await e
    .read<OpenChannelRecord>({ collection: OPEN_CHANNEL_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: OpenChannelRecord }> }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", channelUri: existing.records[0].uri, did: existing.records[0].value.did, channelKey: input.channelKey };
  }
  const now = new Date().toISOString();
  const did = channelDidFor(input.channelKey);
  const record: OpenChannelRecord = {
    did,
    channelKey: input.channelKey,
    platform: input.platform,
    channelId: input.channelId,
    title: input.title,
    description: input.description,
    country: input.country,
    language: input.language,
    channelUrl: input.channelUrl,
    firstSeenAt: input.firstSeenAt ?? now,
    lastSeenAt: input.lastSeenAt ?? now,
    createdAt: now,
  };
  const receipt = await e.write({ collection: OPEN_CHANNEL_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "recorded", channelUri: receipt.uri, did, channelKey: input.channelKey };
}

export async function listChannels(e: Etzhayyim, input: ListChannelsInput = {}): Promise<ListChannelsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<OpenChannelRecord>({ collection: OPEN_CHANNEL_COLLECTION, cursor: input.cursor, limit });
  const items: OpenChannelView[] = resp.records
    .filter((r) => !input.platform || r.value.platform === input.platform)
    .filter((r) => !input.country || r.value.country === input.country)
    .map((r) => ({ ...r.value, channelUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function getChannel(e: Etzhayyim, input: GetChannelInput): Promise<GetChannelOutput> {
  if (!input.channelKey) return { error: "invalidChannelKey" };
  const rkey = channelRkey(input.channelKey);
  const resp = await e
    .read<OpenChannelRecord>({ collection: OPEN_CHANNEL_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: OpenChannelRecord }> }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { channel: { ...r.value, channelUri: r.uri } };
}

// ─── scraperRun (PLAINTEXT operational aggregate) ───────────────────

export async function recordRun(e: Etzhayyim, input: RecordRunInput): Promise<RecordRunOutput> {
  if (!input.runId) return { status: "rejected", error: "missingRequiredFields" };
  if (!isPlatform(input.platform)) return { status: "rejected", error: "invalidPlatform" };
  if (!isRunStatus(input.status)) return { status: "rejected", error: "invalidStatus" };
  if (!isUint(input.messagesSeen) || !isUint(input.messagesNew)) return { status: "rejected", error: "invalidCounts" };
  const rkey = runRkey(input.runId);
  const existing = await e
    .read<ScraperRunRecord>({ collection: SCRAPER_RUN_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: ScraperRunRecord }> }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", runUri: existing.records[0].uri, did: existing.records[0].value.did, runId: input.runId };
  }
  const now = new Date().toISOString();
  const did = runDidFor(input.runId);
  const record: ScraperRunRecord = {
    did,
    runId: input.runId,
    platform: input.platform,
    channelKey: input.channelKey,
    status: input.status,
    messagesSeen: input.messagesSeen,
    messagesNew: input.messagesNew,
    startedAt: input.startedAt ?? now,
    finishedAt: input.finishedAt,
    errorMessage: input.errorMessage,
    createdAt: now,
  };
  const receipt = await e.write({ collection: SCRAPER_RUN_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "recorded", runUri: receipt.uri, did, runId: input.runId };
}

export async function listRuns(e: Etzhayyim, input: ListRunsInput = {}): Promise<ListRunsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ScraperRunRecord>({ collection: SCRAPER_RUN_COLLECTION, cursor: input.cursor, limit });
  const items: ScraperRunView[] = resp.records
    .filter((r) => !input.platform || r.value.platform === input.platform)
    .filter((r) => !input.status || r.value.status === input.status)
    .map((r) => ({ ...r.value, runUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── bridge (E2E control-plane: convoDid + owner) ───────────────────

export async function registerBridge(e: Etzhayyim, input: RegisterBridgeInput): Promise<RegisterBridgeOutput> {
  if (!input.bridgeId || !input.channelId || !input.ownerDid) return { status: "rejected", error: "missingRequiredFields" };
  if (!isPlatform(input.platform)) return { status: "rejected", error: "invalidPlatform" };
  if (!isBridgeMode(input.bridgeMode)) return { status: "rejected", error: "invalidBridgeMode" };
  if (!isE2eMode(input.e2eMode)) return { status: "rejected", error: "invalidE2eMode" };
  const body: BridgeBody = {
    bridgeId: input.bridgeId,
    platform: input.platform,
    channelId: input.channelId,
    channelName: input.channelName,
    ownerDid: input.ownerDid,
    bridgeMode: input.bridgeMode,
    convoDid: input.convoDid,
    e2eMode: input.e2eMode,
    boundAt: input.boundAt ?? new Date().toISOString(),
  };
  // Read-cap = owner DID (sender, auto-wrapped) + the channel owner + recipients.
  const recipients = [...new Set([input.ownerDid, ...(input.recipients ?? [])])];
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: BRIDGE_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients,
    rkey: bridgeRkey(input.bridgeId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, bridgeId: input.bridgeId };
}

async function scanBridges(e: Etzhayyim, maxScan: number): Promise<BridgeView[]> {
  const out: BridgeView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<BridgeBody>({ innerType: BRIDGE_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listBridges(e: Etzhayyim, input: ListBridgesInput = {}): Promise<ListBridgesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanBridges(e, DEFAULT_MAX_SCAN);
  const filtered = all
    .filter((b) => !input.platform || b.platform === input.platform)
    .filter((b) => !input.bridgeMode || b.bridgeMode === input.bridgeMode);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getBridge(e: Etzhayyim, input: GetBridgeInput): Promise<GetBridgeOutput> {
  if (!input.bridgeId) return { error: "invalidBridgeId" };
  const all = await scanBridges(e, DEFAULT_MAX_SCAN);
  const found = all.find((b) => b.bridgeId === input.bridgeId);
  if (!found) return { error: "notFound" };
  return { bridge: found };
}

// ─── openMessage (E2E per-author scraped content) ───────────────────

export async function recordMessage(e: Etzhayyim, input: RecordMessageInput): Promise<RecordMessageOutput> {
  if (!input.messageId || !input.channelKey || !input.platformMessageId) return { status: "rejected", error: "missingRequiredFields" };
  if (!input.authorLabel || !input.messageText) return { status: "rejected", error: "missingRequiredFields" };
  if (!isPlatform(input.platform)) return { status: "rejected", error: "invalidPlatform" };
  // Cross-tier FK: parent openChannel (plaintext catalog) must exist.
  if (!(await channelExists(e, input.channelKey))) return { status: "rejected", error: "channelNotFound" };
  const body: OpenMessageBody = {
    messageId: input.messageId,
    channelKey: input.channelKey,
    platform: input.platform,
    platformMessageId: input.platformMessageId,
    authorLabel: input.authorLabel,
    messageText: input.messageText,
    messageUrl: input.messageUrl,
    publishedAt: input.publishedAt,
    observedAt: input.observedAt ?? new Date().toISOString(),
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: OPEN_MESSAGE_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: messageRkey(input.messageId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, messageId: input.messageId };
}

async function scanMessages(e: Etzhayyim, maxScan: number): Promise<OpenMessageView[]> {
  const out: OpenMessageView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<OpenMessageBody>({ innerType: OPEN_MESSAGE_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listMessages(e: Etzhayyim, input: ListMessagesInput = {}): Promise<ListMessagesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanMessages(e, DEFAULT_MAX_SCAN);
  const filtered = all
    .filter((m) => !input.channelKey || m.channelKey === input.channelKey)
    .filter((m) => !input.platform || m.platform === input.platform);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getMessage(e: Etzhayyim, input: GetMessageInput): Promise<GetMessageOutput> {
  if (!input.messageId) return { error: "invalidMessageId" };
  const all = await scanMessages(e, DEFAULT_MAX_SCAN);
  const found = all.find((m) => m.messageId === input.messageId);
  if (!found) return { error: "notFound" };
  return { message: found };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const channelsByPlatform: Record<string, number> = {};
  let openChannelCount = 0;
  let cursor: string | undefined;
  while (openChannelCount < maxScan) {
    const page = await e.read<OpenChannelRecord>({ collection: OPEN_CHANNEL_COLLECTION, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      channelsByPlatform[r.value.platform] = (channelsByPlatform[r.value.platform] ?? 0) + 1;
      openChannelCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  let scraperRunCount = 0;
  let runCursor: string | undefined;
  while (scraperRunCount < maxScan) {
    const page = await e.read<ScraperRunRecord>({ collection: SCRAPER_RUN_COLLECTION, cursor: runCursor, limit: PAGE_LIMIT });
    scraperRunCount += page.records.length;
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    runCursor = page.cursor;
  }
  const bridgeCount = (await scanBridges(e, maxScan)).length;
  const openMessageCount = (await scanMessages(e, maxScan)).length;
  return {
    openChannelCount,
    scraperRunCount,
    bridgeCount,
    openMessageCount,
    channelsByPlatform,
    truncated:
      openChannelCount >= maxScan ||
      scraperRunCount >= maxScan ||
      bridgeCount >= maxScan ||
      openMessageCount >= maxScan,
  };
}
