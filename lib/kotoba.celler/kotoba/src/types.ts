/**
 * celler kotoba — record types.
 *
 * Per ADR-2605203000 Option B. celler = DID-addressed encrypted telephony over a
 * Starlink mesh. The ONLY substrate-resident state is the owner's own
 * DID ↔ E.164 number provisioning (self-asserted, like a DID document entry).
 *
 * CUSTODY-SAFE (ADR-2605172000 + 3-axis Custody): call content is Signal-E2E and
 * never decryptable server-side; CDR (who-called-whom) is operator-producible
 * PII and is therefore NOT stored on the etzhayyim substrate — no CallRecord /
 * CDR collection exists here. Only the user's own number bindings live on AT PDS.
 *
 * Identity hierarchy:
 *   did:web:celler.kotoba-lang.org                       — controller
 *   did:web:celler.kotoba-lang.org:number:{numberId}     — a provisioned number
 */

export const CELLER_DID_PREFIX = "did:web:celler.kotoba-lang.org:" as const;

export const NUMBER_COLLECTION = "org.kotoba-lang.apps.celler.number";

export type NumberStatus = "active" | "suspended" | "released";

/** Provisioning provider (PSTN bridge). */
export type NumberProvider = "telnyx" | "other";

export interface NumberRecord {
  did: string;
  numberId: string;
  /** DID of the owner who provisioned this number (self-asserted binding). */
  ownerDid: string;
  /** E.164, digits only with leading '+'. */
  e164: string;
  /** ISO 3166-1 alpha-2 country. */
  country: string;
  provider: NumberProvider;
  status: NumberStatus;
  provisionedAt: string;
  createdAt: string;
}

export interface NumberView extends NumberRecord {
  numberUri: string;
}

export interface ProvisionNumberInput {
  numberId: string;
  ownerDid: string;
  e164: string;
  country: string;
  provider?: NumberProvider;
}

export interface ProvisionNumberOutput {
  status: "provisioned" | "alreadyExists" | "rejected";
  numberUri?: string;
  did?: string;
  numberId?: string;
  error?: string;
}

export interface GetNumberInput {
  numberId: string;
}

export interface GetNumberOutput {
  number?: NumberView;
  error?: string;
}

export interface ResolveByE164Input {
  e164: string;
}

export interface ResolveByE164Output {
  number?: NumberView;
  error?: string;
}

export interface ListNumbersInput {
  ownerDid?: string;
  country?: string;
  status?: NumberStatus;
  limit?: number;
  cursor?: string;
}

export interface ListNumbersOutput {
  items: NumberView[];
  cursor?: string;
  total: number;
}

export interface ReleaseNumberInput {
  numberId: string;
}

export interface ReleaseNumberOutput {
  status: "released" | "notFound" | "alreadyReleased";
  numberId?: string;
  error?: string;
}

export interface CoverageInput {
  maxScan?: number;
}

export interface CoverageOutput {
  total?: number;
  byCountry?: Record<string, number>;
  byStatus?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Helpers ────────────────────────────────────────────────────────

const RE_E164 = /^\+[1-9]\d{6,14}$/;

export function isValidE164(n: string): boolean {
  return RE_E164.test(n);
}

export function normalizeE164(n: string): string {
  return n.trim().replace(/[^\d+]/g, "");
}

export function numberDid(numberId: string): string {
  return `${CELLER_DID_PREFIX}number:${numberId.toLowerCase()}`;
}

export function numberRkey(numberId: string): string {
  return `number-${numberId.toLowerCase()}`;
}
