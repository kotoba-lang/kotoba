/**
 * common-crawl kotoba — snapshot catalog registry (slice 1, 4/4 canonical).
 *
 *   registerCrawl — register a CC-MAIN batch (rkey=cc_main_yyyy_ww, idempotent).
 *                   Validates the CC-MAIN-YYYY-WW id; derives year + week.
 *   getCrawl      — by crawlId.
 *   listCrawls    — cursor + year/status/format filter.
 *   coverage      — counts by year + status, plus summed pageCount.
 *
 * Replaces vendor createKyselyDb()/vertex_crawl_batch with AT PDS records (no
 * RW). Catalog metadata is public → 3-axis clean.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  crawlDid,
  crawlRkey,
  isValidCrawlId,
  parseCrawlId,
  type CoverageInput,
  type CoverageOutput,
  type CrawlBatchRecord,
  type CrawlBatchView,
  type CrawlStatus,
  type GetCrawlInput,
  type GetCrawlOutput,
  type ListCrawlsInput,
  type ListCrawlsOutput,
  type RegisterCrawlInput,
  type RegisterCrawlOutput,
} from "./types.js";

const CRAWL_COLLECTION = "com.etzhayyim.apps.commonCrawl.crawlBatch";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

export async function registerCrawl(
  e: Etzhayyim,
  input: RegisterCrawlInput
): Promise<RegisterCrawlOutput> {
  if (!input.crawlId) return { status: "rejected", error: "missingCrawlId" };
  if (!isValidCrawlId(input.crawlId)) {
    return { status: "rejected", error: "invalidCrawlId" };
  }
  const { year, week } = parseCrawlId(input.crawlId);

  const rkey = crawlRkey(input.crawlId);
  const existing = await e
    .read<CrawlBatchRecord>({ collection: CRAWL_COLLECTION, rkey })
    .catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return {
      status: "alreadyExists",
      crawlUri: existing.records[0].uri,
      did: existing.records[0].value.did,
      crawlId: input.crawlId,
    };
  }

  const did = crawlDid(input.crawlId);
  const now = new Date().toISOString();
  const record: CrawlBatchRecord = {
    did,
    crawlId: input.crawlId,
    year,
    week,
    startDate: input.startDate,
    endDate: input.endDate,
    formats: input.formats,
    fileCount: input.fileCount,
    pageCount: input.pageCount,
    status: input.status ?? "available",
    source: input.source ?? "commoncrawl.org",
    sourceUrl: input.sourceUrl,
    collectedAt: now,
    createdAt: now,
  };
  const receipt = await e.write({
    collection: CRAWL_COLLECTION,
    record: record as unknown as Record<string, unknown>,
    rkey,
  });
  return { status: "registered", crawlUri: receipt.uri, did, crawlId: input.crawlId };
}

export async function getCrawl(
  e: Etzhayyim,
  input: GetCrawlInput
): Promise<GetCrawlOutput> {
  if (!input.crawlId || !isValidCrawlId(input.crawlId)) {
    return { error: "invalidCrawlId" };
  }
  const resp = await e
    .read<CrawlBatchRecord>({
      collection: CRAWL_COLLECTION,
      rkey: crawlRkey(input.crawlId),
    })
    .catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { crawl: { ...r.value, crawlUri: r.uri } };
}

export async function listCrawls(
  e: Etzhayyim,
  input: ListCrawlsInput = {}
): Promise<ListCrawlsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<CrawlBatchRecord>({
    collection: CRAWL_COLLECTION,
    cursor: input.cursor,
    limit,
  });
  const items: CrawlBatchView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.year && v.year !== input.year) return false;
      if (input.status && v.status !== input.status) return false;
      if (input.format && !(v.formats ?? []).includes(input.format)) return false;
      return true;
    })
    .map((r) => ({ ...r.value, crawlUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function coverage(
  e: Etzhayyim,
  input: CoverageInput = {}
): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  let cursor: string | undefined;
  let scanned = 0;
  const byYear: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  let totalPages = 0;
  while (scanned < maxScan) {
    const page = await e.read<CrawlBatchRecord>({
      collection: CRAWL_COLLECTION,
      cursor,
      limit: PAGE_LIMIT,
    });
    for (const r of page.records) {
      if (scanned >= maxScan) break;
      const v = r.value;
      byYear[String(v.year)] = (byYear[String(v.year)] ?? 0) + 1;
      byStatus[v.status as CrawlStatus] = (byStatus[v.status as CrawlStatus] ?? 0) + 1;
      if (typeof v.pageCount === "number") totalPages += v.pageCount;
      scanned += 1;
    }
    if (scanned >= maxScan || !page.cursor || page.records.length < PAGE_LIMIT) {
      break;
    }
    cursor = page.cursor;
  }
  return {
    total: scanned,
    byYear,
    byStatus,
    totalPages,
    truncated: scanned >= maxScan,
  };
}
