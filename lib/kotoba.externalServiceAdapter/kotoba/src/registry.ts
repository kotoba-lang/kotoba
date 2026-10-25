/**
 * external-service-adapter kotoba — kotoba-E2E registry.
 *
 * Plaintext path (providerConnector): sdk.write / sdk.read — public reference
 * catalog of supported external services.
 * E2E path (mailboxSync, oauthGrant): sdk.encryptedWrite / sdk.encryptedRead —
 * per-person account-linkage metadata sealed in the kotoba envelope
 * (ADR-2605181100), read-cap = owner DID + explicit recipients. The substrate
 * never sees which inbox a person linked, nor their grant scopes, in plaintext.
 *
 * STAYS etzhayyim (consent-capability, not a collection): OAuth access/refresh-token
 * + client-secret custody, and the external Graph/Gmail/Drive API CALL itself.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  MAILBOX_SYNC_INNER_TYPE,
  OAUTH_GRANT_INNER_TYPE,
  PROVIDER_CONNECTOR_COLLECTION,
  connectorDidFor,
  isOauthStatus,
  isUint,
  rkeyOf,
  type CoverageInput,
  type CoverageOutput,
  type GetConnectorInput,
  type GetConnectorOutput,
  type GetGrantInput,
  type GetGrantOutput,
  type GetSyncInput,
  type GetSyncOutput,
  type ListConnectorsInput,
  type ListConnectorsOutput,
  type ListGrantsInput,
  type ListGrantsOutput,
  type ListSyncsInput,
  type ListSyncsOutput,
  type MailboxSyncBody,
  type MailboxSyncView,
  type OauthGrantBody,
  type OauthGrantView,
  type ProviderConnectorRecord,
  type ProviderConnectorView,
  type RecordGrantInput,
  type RecordGrantOutput,
  type RecordSyncInput,
  type RecordSyncOutput,
  type RegisterConnectorInput,
  type RegisterConnectorOutput,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

// ─── Provider connector (PLAINTEXT public catalog) ──────────────────

export async function registerConnector(e: Etzhayyim, input: RegisterConnectorInput): Promise<RegisterConnectorOutput> {
  if (!input.provider || !input.displayName || !input.category || !input.apiBase) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const rkey = rkeyOf("conn", input.provider);
  const existing = await e
    .read<ProviderConnectorRecord>({ collection: PROVIDER_CONNECTOR_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: ProviderConnectorRecord }> }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", connectorUri: existing.records[0].uri, did: existing.records[0].value.did, provider: input.provider };
  }
  const now = new Date().toISOString();
  const did = connectorDidFor(input.provider);
  const record: ProviderConnectorRecord = {
    did,
    provider: input.provider,
    displayName: input.displayName,
    category: input.category,
    apiBase: input.apiBase,
    scopes: input.scopes ?? [],
    createdAt: now,
  };
  const receipt = await e.write({ collection: PROVIDER_CONNECTOR_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "registered", connectorUri: receipt.uri, did, provider: input.provider };
}

export async function getConnector(e: Etzhayyim, input: GetConnectorInput): Promise<GetConnectorOutput> {
  if (!input.provider) return { error: "invalidProvider" };
  const rkey = rkeyOf("conn", input.provider);
  const resp = await e
    .read<ProviderConnectorRecord>({ collection: PROVIDER_CONNECTOR_COLLECTION, rkey })
    .catch(() => ({ records: [] as Array<{ uri: string; value: ProviderConnectorRecord }> }));
  const r = resp.records[0];
  if (!r?.value) return { error: "notFound" };
  return { connector: { ...r.value, connectorUri: r.uri } };
}

export async function listConnectors(e: Etzhayyim, input: ListConnectorsInput = {}): Promise<ListConnectorsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ProviderConnectorRecord>({ collection: PROVIDER_CONNECTOR_COLLECTION, cursor: input.cursor, limit });
  const items: ProviderConnectorView[] = resp.records
    .filter((r) => !input.category || r.value.category === input.category)
    .map((r) => ({ ...r.value, connectorUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Mailbox sync (E2E-ENCRYPTED per-person) ────────────────────────

export async function recordSync(e: Etzhayyim, input: RecordSyncInput): Promise<RecordSyncOutput> {
  if (!input.syncId || !input.userDid || !input.provider) return { status: "rejected", error: "missingRequiredFields" };
  if (!isUint(input.messagesIngested)) return { status: "rejected", error: "invalidMessagesIngested" };
  if (input.oauthStatus !== undefined && !isOauthStatus(input.oauthStatus)) return { status: "rejected", error: "invalidOauthStatus" };
  const now = new Date().toISOString();
  const body: MailboxSyncBody = {
    syncId: input.syncId,
    userDid: input.userDid,
    provider: input.provider,
    folder: input.folder ?? "INBOX",
    messagesIngested: input.messagesIngested,
    watermark: input.watermark ?? "",
    oauthStatus: input.oauthStatus ?? "connected",
    lastSyncAt: input.lastSyncAt ?? now,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: MAILBOX_SYNC_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("sync", input.syncId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, syncId: input.syncId };
}

async function scanSyncs(e: Etzhayyim, maxScan: number): Promise<MailboxSyncView[]> {
  const out: MailboxSyncView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<MailboxSyncBody>({ innerType: MAILBOX_SYNC_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listSyncs(e: Etzhayyim, input: ListSyncsInput = {}): Promise<ListSyncsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanSyncs(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((s) => !input.provider || s.provider === input.provider);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getSync(e: Etzhayyim, input: GetSyncInput): Promise<GetSyncOutput> {
  if (!input.syncId) return { error: "invalidSyncId" };
  const all = await scanSyncs(e, DEFAULT_MAX_SCAN);
  const found = all.find((s) => s.syncId === input.syncId);
  if (!found) return { error: "notFound" };
  return { sync: found };
}

// ─── OAuth grant (E2E-ENCRYPTED binding metadata ONLY) ──────────────

export async function recordGrant(e: Etzhayyim, input: RecordGrantInput): Promise<RecordGrantOutput> {
  if (!input.grantId || !input.userDid || !input.provider) return { status: "rejected", error: "missingRequiredFields" };
  if (input.status !== undefined && !isOauthStatus(input.status)) return { status: "rejected", error: "invalidStatus" };
  const now = new Date().toISOString();
  const body: OauthGrantBody = {
    grantId: input.grantId,
    userDid: input.userDid,
    provider: input.provider,
    scopes: input.scopes ?? [],
    status: input.status ?? "connected",
    grantedAt: input.grantedAt ?? now,
    expiresAt: input.expiresAt ?? now,
  };
  const receipt = await e.encryptedWrite<Record<string, unknown>>({
    innerType: OAUTH_GRANT_INNER_TYPE,
    record: body as unknown as Record<string, unknown>,
    recipients: input.recipients ?? [],
    rkey: rkeyOf("grant", input.grantId),
  });
  return { status: "recorded", uri: receipt.uri, keyId: receipt.keyId, grantId: input.grantId };
}

async function scanGrants(e: Etzhayyim, maxScan: number): Promise<OauthGrantView[]> {
  const out: OauthGrantView[] = [];
  let cursor: string | undefined;
  while (out.length < maxScan) {
    const page = await e.encryptedRead<OauthGrantBody>({ innerType: OAUTH_GRANT_INNER_TYPE, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      out.push({ ...r.value, uri: r.uri, sender: r.sender, createdAt: r.createdAt });
    }
    if (!page.cursor || page.records.length === 0) break;
    cursor = page.cursor;
  }
  return out;
}

export async function listGrants(e: Etzhayyim, input: ListGrantsInput = {}): Promise<ListGrantsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const all = await scanGrants(e, DEFAULT_MAX_SCAN);
  const filtered = all.filter((g) => !input.provider || g.provider === input.provider);
  return { items: filtered.slice(0, limit), total: filtered.length };
}

export async function getGrant(e: Etzhayyim, input: GetGrantInput): Promise<GetGrantOutput> {
  if (!input.grantId) return { error: "invalidGrantId" };
  const all = await scanGrants(e, DEFAULT_MAX_SCAN);
  const found = all.find((g) => g.grantId === input.grantId);
  if (!found) return { error: "notFound" };
  return { grant: found };
}

// ─── Coverage rollup ────────────────────────────────────────────────

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const connectorsByCategory: Record<string, number> = {};
  let providerConnectorCount = 0;
  let cursor: string | undefined;
  while (providerConnectorCount < maxScan) {
    const page = await e.read<ProviderConnectorRecord>({ collection: PROVIDER_CONNECTOR_COLLECTION, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      connectorsByCategory[r.value.category] = (connectorsByCategory[r.value.category] ?? 0) + 1;
      providerConnectorCount += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  const mailboxSyncCount = (await scanSyncs(e, maxScan)).length;
  const oauthGrantCount = (await scanGrants(e, maxScan)).length;
  return {
    providerConnectorCount,
    mailboxSyncCount,
    oauthGrantCount,
    connectorsByCategory,
    truncated: providerConnectorCount >= maxScan || mailboxSyncCount >= maxScan || oauthGrantCount >= maxScan,
  };
}
