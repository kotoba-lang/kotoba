/**
 * external-service-adapter kotoba — kotoba-E2E split.
 *
 * Per ADR-2606011400 (Consensys product-front/infra-back) + ADR-2605172400
 * (3-axis Liability/Custody/Settlement) + ADR-2605181100 (kotoba E2E
 * encrypted-record envelope). Founder directive 2026-06-03: front everything
 * that can move; only the irreducible regulated EXECUTION stays etzhayyim.
 *
 * This app integrates external mailboxes / calendars / drives (Microsoft 365 +
 * Google Workspace) over OAuth2 and records per-user sync state.
 *
 * SPLIT:
 *   PLAINTEXT (public reference catalog, no subject data) —
 *     providerConnector: the catalog of supported external services
 *     (provider id, displayName, apiBase, scopes, category). Frontable open
 *     reference metadata; nothing per-person.
 *
 *   E2E (kotoba envelope, com.etzhayyim.encrypted.record) — per-person
 *   account-linkage metadata, read-cap = owner DID + explicit recipients:
 *     mailboxSync: userDid + provider + folder + watermark + counts +
 *       oauthStatus (which inbox a person linked, and how far it synced).
 *     oauthGrant: userDid + provider + granted scopes + status + expiry —
 *       BINDING METADATA ONLY (see staysEtzhayyim: the raw access/refresh tokens
 *       and client secrets are NEVER part of this body).
 *
 *   STAYS etzhayyim (consumed via consent-capability, NOT a collection) — the
 *   irreducible regulated EXECUTION:
 *     * OAuth access-token / refresh-token / client-secret raw custody
 *       (credential/secret/raw-key custody).
 *     * The external Microsoft Graph / Gmail / Drive API CALL execution
 *       (the regulated outbound act against the third-party rail).
 *   The sync/grant DATA fronts E2E; the token custody + the API call stay etzhayyim.
 *
 * AT-Lexicon: no float — counts (messagesIngested) are integers; expiry/grant
 * timestamps are ISO strings.
 */

// Plaintext public collection.
export const PROVIDER_CONNECTOR_COLLECTION = "com.etzhayyim.apps.externalServiceAdapter.providerConnector";
// E2E inner-type NSIDs (body shape inside the encrypted envelope).
export const MAILBOX_SYNC_INNER_TYPE = "com.etzhayyim.apps.externalServiceAdapter.mailboxSync";
export const OAUTH_GRANT_INNER_TYPE = "com.etzhayyim.apps.externalServiceAdapter.oauthGrant";

export const ESA_DID_PREFIX = "did:web:external-service-adapter.etzhayyim.com:" as const;

export type OauthStatus = "connected" | "expired" | "revoked";

// ─── Provider connector (PLAINTEXT, public reference catalog) ────────

export interface ProviderConnectorRecord {
  did: string;
  provider: string;
  displayName: string;
  category: string;
  apiBase: string;
  scopes: string[];
  createdAt: string;
}
export interface ProviderConnectorView extends ProviderConnectorRecord {
  connectorUri: string;
}
export interface RegisterConnectorInput {
  provider: string;
  displayName: string;
  category: string;
  apiBase: string;
  scopes?: string[];
}
export interface RegisterConnectorOutput {
  status: "registered" | "alreadyExists" | "rejected";
  connectorUri?: string;
  did?: string;
  provider?: string;
  error?: string;
}
export interface GetConnectorInput {
  provider: string;
}
export interface GetConnectorOutput {
  connector?: ProviderConnectorView;
  error?: string;
}
export interface ListConnectorsInput {
  category?: string;
  limit?: number;
  cursor?: string;
}
export interface ListConnectorsOutput {
  items: ProviderConnectorView[];
  cursor?: string;
  total: number;
}

// ─── Mailbox sync (E2E-ENCRYPTED, per-person account linkage) ───────

export interface MailboxSyncBody {
  syncId: string;
  userDid: string;
  provider: string;
  folder: string;
  messagesIngested: number;
  watermark: string;
  oauthStatus: OauthStatus;
  lastSyncAt: string;
}
export interface MailboxSyncView extends MailboxSyncBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordSyncInput {
  syncId: string;
  userDid: string;
  provider: string;
  folder?: string;
  messagesIngested: number;
  watermark?: string;
  oauthStatus?: OauthStatus;
  lastSyncAt?: string;
  /** Extra DIDs to grant read-cap (owner always included). */
  recipients?: string[];
}
export interface RecordSyncOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  syncId?: string;
  error?: string;
}
export interface ListSyncsInput {
  provider?: string;
  limit?: number;
  cursor?: string;
}
export interface ListSyncsOutput {
  items: MailboxSyncView[];
  cursor?: string;
  total: number;
}
export interface GetSyncInput {
  syncId: string;
}
export interface GetSyncOutput {
  sync?: MailboxSyncView;
  error?: string;
}

// ─── OAuth grant (E2E-ENCRYPTED, binding metadata ONLY) ─────────────
// NOTE: raw access/refresh tokens + client secrets are NEVER in this body —
// that custody stays etzhayyim (see module header staysEtzhayyim).

export interface OauthGrantBody {
  grantId: string;
  userDid: string;
  provider: string;
  scopes: string[];
  status: OauthStatus;
  grantedAt: string;
  expiresAt: string;
}
export interface OauthGrantView extends OauthGrantBody {
  uri: string;
  sender: string;
  createdAt: string;
}
export interface RecordGrantInput {
  grantId: string;
  userDid: string;
  provider: string;
  scopes?: string[];
  status?: OauthStatus;
  grantedAt?: string;
  expiresAt?: string;
  recipients?: string[];
}
export interface RecordGrantOutput {
  status: "recorded" | "rejected";
  uri?: string;
  keyId?: string;
  grantId?: string;
  error?: string;
}
export interface ListGrantsInput {
  provider?: string;
  limit?: number;
  cursor?: string;
}
export interface ListGrantsOutput {
  items: OauthGrantView[];
  cursor?: string;
  total: number;
}
export interface GetGrantInput {
  grantId: string;
}
export interface GetGrantOutput {
  grant?: OauthGrantView;
  error?: string;
}

// ─── Coverage rollup ────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  providerConnectorCount?: number;
  mailboxSyncCount?: number;
  oauthGrantCount?: number;
  connectorsByCategory?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Validation + helpers ───────────────────────────────────────────

const OAUTH_STATUSES: readonly OauthStatus[] = ["connected", "expired", "revoked"];

export function isUint(n: unknown): n is number {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}
export function isOauthStatus(s: unknown): s is OauthStatus {
  return typeof s === "string" && (OAUTH_STATUSES as readonly string[]).includes(s);
}
export function connectorDidFor(provider: string): string {
  return `${ESA_DID_PREFIX}conn:${provider.toLowerCase()}`;
}
export function rkeyOf(prefix: string, id: string): string {
  return `${prefix}-${id.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
