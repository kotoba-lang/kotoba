/**
 * common-crawl kotoba — barrel.
 *
 * Per ADR-2605203000 Option B Phase E reference impl. Common Crawl snapshot
 * catalog (CC-MAIN-YYYY-WW) on the etzhayyim substrate (AT PDS records; no RW).
 *
 * Slice 1: 4 of 4 canonical lexicons ported.
 *   registerCrawl + getCrawl + listCrawls + coverage
 */

export * from "./types.js";
export { registerCrawl, getCrawl, listCrawls, coverage } from "./registry.js";
