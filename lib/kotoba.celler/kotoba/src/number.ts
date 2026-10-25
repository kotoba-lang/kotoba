/**
 * celler kotoba — number-provisioning registry. AT PDS records (no RW).
 * provisionNumber / getNumber / resolveByE164 / listNumbers / releaseNumber /
 * coverage. No CDR / call content — those are Signal-E2E and not server-stored.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  NUMBER_COLLECTION,
  isValidE164,
  normalizeE164,
  numberDid,
  numberRkey,
  type CoverageInput,
  type CoverageOutput,
  type GetNumberInput,
  type GetNumberOutput,
  type ListNumbersInput,
  type ListNumbersOutput,
  type NumberProvider,
  type NumberRecord,
  type NumberStatus,
  type NumberView,
  type ProvisionNumberInput,
  type ProvisionNumberOutput,
  type ReleaseNumberInput,
  type ReleaseNumberOutput,
  type ResolveByE164Input,
  type ResolveByE164Output,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

export async function provisionNumber(
  e: Etzhayyim,
  input: ProvisionNumberInput
): Promise<ProvisionNumberOutput> {
  if (!input.numberId || !input.ownerDid || !input.e164 || !input.country) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  const e164 = normalizeE164(input.e164);
  if (!isValidE164(e164)) return { status: "rejected", error: "invalidE164" };
  if (!/^[A-Z]{2}$/.test(input.country)) {
    return { status: "rejected", error: "invalidCountry" };
  }

  const rkey = numberRkey(input.numberId);
  const existing = await e
    .read<NumberRecord>({ collection: NUMBER_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return {
      status: "alreadyExists",
      numberUri: existing.records[0].uri,
      did: existing.records[0].value.did,
      numberId: input.numberId,
    };
  }

  const did = numberDid(input.numberId);
  const now = new Date().toISOString();
  const record: NumberRecord = {
    did,
    numberId: input.numberId,
    ownerDid: input.ownerDid,
    e164,
    country: input.country,
    provider: input.provider ?? "telnyx",
    status: "active",
    provisionedAt: now,
    createdAt: now,
  };
  const receipt = await e.write({
    collection: NUMBER_COLLECTION,
    record: record as unknown as Record<string, unknown>,
    rkey,
  });
  return { status: "provisioned", numberUri: receipt.uri, did, numberId: input.numberId };
}

export async function getNumber(
  e: Etzhayyim,
  input: GetNumberInput
): Promise<GetNumberOutput> {
  if (!input.numberId) return { error: "invalidNumberId" };
  const resp = await e
    .read<NumberRecord>({ collection: NUMBER_COLLECTION, rkey: numberRkey(input.numberId) })
    .catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { number: { ...r.value, numberUri: r.uri } };
}

/** Resolve an active number by E.164 (linear scan; small per-owner sets). */
export async function resolveByE164(
  e: Etzhayyim,
  input: ResolveByE164Input
): Promise<ResolveByE164Output> {
  const e164 = normalizeE164(input.e164 ?? "");
  if (!isValidE164(e164)) return { error: "invalidE164" };
  let cursor: string | undefined;
  let scanned = 0;
  while (scanned < DEFAULT_MAX_SCAN) {
    const page = await e.read<NumberRecord>({
      collection: NUMBER_COLLECTION,
      cursor,
      limit: PAGE_LIMIT,
    });
    for (const r of page.records) {
      if (r.value.e164 === e164 && r.value.status !== "released") {
        return { number: { ...r.value, numberUri: r.uri } };
      }
      scanned += 1;
    }
    if (!page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return { error: "notFound" };
}

export async function listNumbers(
  e: Etzhayyim,
  input: ListNumbersInput = {}
): Promise<ListNumbersOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<NumberRecord>({
    collection: NUMBER_COLLECTION,
    cursor: input.cursor,
    limit,
  });
  const items: NumberView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.ownerDid && v.ownerDid !== input.ownerDid) return false;
      if (input.country && v.country !== input.country) return false;
      if (input.status && v.status !== input.status) return false;
      return true;
    })
    .map((r) => ({ ...r.value, numberUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function releaseNumber(
  e: Etzhayyim,
  input: ReleaseNumberInput
): Promise<ReleaseNumberOutput> {
  if (!input.numberId) return { status: "notFound", error: "invalidNumberId" };
  const rkey = numberRkey(input.numberId);
  const resp = await e
    .read<NumberRecord>({ collection: NUMBER_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  const num = resp.records[0]?.value;
  if (!num) return { status: "notFound", error: "numberNotFound" };
  if (num.status === "released") return { status: "alreadyReleased", numberId: input.numberId };
  await e.write({
    collection: NUMBER_COLLECTION,
    record: { ...num, status: "released" } as unknown as Record<string, unknown>,
    rkey,
  });
  return { status: "released", numberId: input.numberId };
}

export async function coverage(
  e: Etzhayyim,
  input: CoverageInput = {}
): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  let cursor: string | undefined;
  let scanned = 0;
  const byCountry: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  while (scanned < maxScan) {
    const page = await e.read<NumberRecord>({
      collection: NUMBER_COLLECTION,
      cursor,
      limit: PAGE_LIMIT,
    });
    for (const r of page.records) {
      if (scanned >= maxScan) break;
      const v = r.value;
      byCountry[v.country] = (byCountry[v.country] ?? 0) + 1;
      byStatus[v.status as NumberStatus] = (byStatus[v.status as NumberStatus] ?? 0) + 1;
      scanned += 1;
    }
    if (scanned >= maxScan || !page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return { total: scanned, byCountry, byStatus, truncated: scanned >= maxScan };
}

export type { NumberProvider };
