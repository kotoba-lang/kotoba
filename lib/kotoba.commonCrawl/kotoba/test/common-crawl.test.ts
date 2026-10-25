import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerCrawl,
  getCrawl,
  listCrawls,
  coverage,
  isValidCrawlId,
  parseCrawlId,
  crawlDid,
  crawlRkey,
} from "../src/index.js";

describe("common-crawl kotoba", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: "did:web:common-crawl.etzhayyim.com" });
  });

  describe("crawlId helpers", () => {
    it("validates CC-MAIN-YYYY-WW", () => {
      expect(isValidCrawlId("CC-MAIN-2026-12")).toBe(true);
      expect(isValidCrawlId("CC-MAIN-2024-05")).toBe(true);
      expect(isValidCrawlId("CC-MAIN-2026-54")).toBe(false); // week > 53
      expect(isValidCrawlId("CC-MAIN-2026-00")).toBe(false); // week < 1
      expect(isValidCrawlId("CC-MAIN-26-12")).toBe(false);
      expect(isValidCrawlId("cc-main-2026-12")).toBe(false);
    });
    it("parses year + week", () => {
      expect(parseCrawlId("CC-MAIN-2026-12")).toEqual({ year: 2026, week: 12 });
      expect(() => parseCrawlId("bad")).toThrow();
    });
    it("derives did + rkey", () => {
      expect(crawlDid("CC-MAIN-2026-12")).toBe(
        "did:web:common-crawl.etzhayyim.com:crawl:CC-MAIN-2026-12"
      );
      expect(crawlRkey("CC-MAIN-2026-12")).toBe("cc_main_2026_12");
    });
  });

  describe("registerCrawl", () => {
    const cc = {
      crawlId: "CC-MAIN-2026-12",
      formats: ["wat", "wet", "warc"] as const,
      fileCount: 49591,
      pageCount: 3_100_000_000,
      status: "available" as const,
    };
    it("registers + derives year/week", async () => {
      const r = await registerCrawl(e, cc);
      expect(r.status).toBe("registered");
      const got = await getCrawl(e, { crawlId: "CC-MAIN-2026-12" });
      expect(got.crawl?.year).toBe(2026);
      expect(got.crawl?.week).toBe(12);
      expect(got.crawl?.source).toBe("commoncrawl.org");
    });
    it("is idempotent on crawlId", async () => {
      await registerCrawl(e, cc);
      const again = await registerCrawl(e, cc);
      expect(again.status).toBe("alreadyExists");
    });
    it("rejects an invalid crawlId", async () => {
      const r = await registerCrawl(e, { crawlId: "CC-MAIN-2026-99" });
      expect(r.status).toBe("rejected");
      expect(r.error).toBe("invalidCrawlId");
    });
  });

  describe("list + coverage", () => {
    beforeEach(async () => {
      await registerCrawl(e, {
        crawlId: "CC-MAIN-2026-12",
        formats: ["wat"],
        pageCount: 3_000_000_000,
        status: "available",
      });
      await registerCrawl(e, {
        crawlId: "CC-MAIN-2025-50",
        formats: ["warc"],
        pageCount: 2_500_000_000,
        status: "archived",
      });
    });
    it("filters by year", async () => {
      const y = await listCrawls(e, { year: 2026 });
      expect(y.total).toBe(1);
      expect(y.items[0].crawlId).toBe("CC-MAIN-2026-12");
    });
    it("filters by format", async () => {
      const warc = await listCrawls(e, { format: "warc" });
      expect(warc.total).toBe(1);
    });
    it("coverage sums pages + counts by year/status", async () => {
      const cov = await coverage(e);
      expect(cov.total).toBe(2);
      expect(cov.byYear?.["2026"]).toBe(1);
      expect(cov.byStatus?.available).toBe(1);
      expect(cov.byStatus?.archived).toBe(1);
      expect(cov.totalPages).toBe(5_500_000_000);
    });
  });
});
