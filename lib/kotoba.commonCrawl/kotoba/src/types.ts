/**
 * common-crawl kotoba — record types.
 *
 * Per ADR-2605203000 Option B (PDS XRPC). Catalog of Common Crawl monthly
 * snapshots (CC-MAIN-YYYY-WW). Public crawl-batch metadata only — the page-level
 * corpus (billions of pages) stays in the heavy pipeline; this registry holds
 * the snapshot catalog, which is public and 3-axis clean. ADR-2605172000 kotoba.
 *
 * Identity hierarchy:
 *   did:web:common-crawl.etzhayyim.com                         — controller
 *   did:web:common-crawl.etzhayyim.com:crawl:CC-MAIN-2026-12   — a crawl batch
 */

export const CC_DID_PREFIX = "did:web:common-crawl.etzhayyim.com:" as const;

/** WARC file families published per crawl. */
export type CrawlFormat = "warc" | "wat" | "wet";

export type CrawlStatus = "announced" | "available" | "archived";

export interface CrawlBatchRecord {
  did: string;
  /** Canonical crawl id, e.g. "CC-MAIN-2026-12" (key). */
  crawlId: string;
  /** 4-digit year, parsed from crawlId. */
  year: number;
  /** ISO week number (1–53), parsed from crawlId. */
  week: number;
  startDate?: string;
  endDate?: string;
  /** Which file families are published for this crawl. */
  formats?: CrawlFormat[];
  fileCount?: number;
  /** Approximate captured pages (large; stored as a number for catalog stats). */
  pageCount?: number;
  status: CrawlStatus;
  source?: string;
  sourceUrl?: string;
  collectedAt: string;
  createdAt: string;
}

export interface CrawlBatchView extends CrawlBatchRecord {
  crawlUri: string;
}

export interface RegisterCrawlInput {
  crawlId: string;
  startDate?: string;
  endDate?: string;
  formats?: CrawlFormat[];
  fileCount?: number;
  pageCount?: number;
  status?: CrawlStatus;
  source?: string;
  sourceUrl?: string;
}

export interface RegisterCrawlOutput {
  status: "registered" | "alreadyExists" | "rejected";
  crawlUri?: string;
  did?: string;
  crawlId?: string;
  error?: string;
}

export interface GetCrawlInput {
  crawlId: string;
}

export interface GetCrawlOutput {
  crawl?: CrawlBatchView;
  error?: string;
}

export interface ListCrawlsInput {
  year?: number;
  status?: CrawlStatus;
  format?: CrawlFormat;
  limit?: number;
  cursor?: string;
}

export interface ListCrawlsOutput {
  items: CrawlBatchView[];
  cursor?: string;
  total: number;
}

export interface CoverageInput {
  maxScan?: number;
}

export interface CoverageOutput {
  total?: number;
  byYear?: Record<string, number>;
  byStatus?: Record<string, number>;
  totalPages?: number;
  truncated?: boolean;
  error?: string;
}

// ─── Helpers ────────────────────────────────────────────────────────

const RE_CRAWL_ID = /^CC-MAIN-(\d{4})-(\d{2})$/;

/** True for a canonical "CC-MAIN-YYYY-WW" id with a 1–53 week. */
export function isValidCrawlId(crawlId: string): boolean {
  const m = RE_CRAWL_ID.exec(crawlId);
  if (!m) return false;
  const week = Number(m[2]);
  return week >= 1 && week <= 53;
}

/** Parse year + ISO week from a crawl id (throws if malformed). */
export function parseCrawlId(crawlId: string): { year: number; week: number } {
  const m = RE_CRAWL_ID.exec(crawlId);
  if (!m) throw new Error(`invalid crawlId: ${crawlId}`);
  const year = Number(m[1]);
  const week = Number(m[2]);
  if (week < 1 || week > 53) throw new Error(`invalid crawl week: ${crawlId}`);
  return { year, week };
}

export function crawlDid(crawlId: string): string {
  return `${CC_DID_PREFIX}crawl:${crawlId}`;
}

export function crawlRkey(crawlId: string): string {
  return crawlId.toLowerCase().replace(/-/g, "_");
}
