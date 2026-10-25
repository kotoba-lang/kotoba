import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  defineEntity,
  getEntity,
  listEntities,
  archiveEntity,
  recordEvent,
  listEvents,
  submitReport,
  publishReport,
  listReports,
  coverage,
} from "../src/index.js";

describe("aima kotoba", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: "did:web:aima.etzhayyim.com" });
  });

  describe("entity graph", () => {
    it("defines, reads, lists by kind + app-layer search, archives", async () => {
      expect((await defineEntity(e, { entityId: "EN-1", name: "Acme Corp", kind: "org", category: "tech" })).status).toBe("defined");
      expect((await getEntity(e, { entityId: "EN-1" })).entity?.status).toBe("active");
      await defineEntity(e, { entityId: "EN-2", name: "RAG Topic", kind: "topic" });
      expect((await listEntities(e, { kind: "org" })).total).toBe(1);
      expect((await listEntities(e, { q: "acme" })).total).toBe(1);
      expect((await defineEntity(e, { entityId: "EN-1", name: "dup", kind: "org" })).status).toBe("alreadyExists");
      expect((await defineEntity(e, { entityId: "EN-X", name: "", kind: "org" })).status).toBe("rejected");
      expect((await archiveEntity(e, { entityId: "EN-1" })).status).toBe("archived");
      expect((await listEntities(e, { status: "active" })).total).toBe(1);
      expect((await archiveEntity(e, { entityId: "EN-1" })).status).toBe("rejected"); // already archived
    });
  });

  describe("events + reports against an entity", () => {
    beforeEach(async () => {
      await defineEntity(e, { entityId: "EN-1", name: "Acme Corp", kind: "org" });
    });
    it("records events (FK) and rejects missing entity; filters by type/since", async () => {
      expect((await recordEvent(e, { eventId: "EV-1", entityId: "EN-1", eventType: "mention", occurredAt: "2026-06-01T00:00:00Z" })).status).toBe("recorded");
      expect((await recordEvent(e, { eventId: "EV-X", entityId: "GHOST", eventType: "mention", occurredAt: "2026-06-01T00:00:00Z" })).status).toBe("entityNotFound");
      await recordEvent(e, { eventId: "EV-2", entityId: "EN-1", eventType: "alert", occurredAt: "2026-06-05T00:00:00Z" });
      expect((await listEvents(e, { entityId: "EN-1", eventType: "alert" })).total).toBe(1);
      expect((await listEvents(e, { since: "2026-06-03T00:00:00Z" })).total).toBe(1);
    });
    it("submits + publishes reports (optional FK), guards republish + bad entity", async () => {
      expect((await submitReport(e, { reportId: "R-1", reportType: "summary", title: "Q2 Brief", entityId: "EN-1" })).status).toBe("submitted");
      // cross-entity report with no FK is allowed
      expect((await submitReport(e, { reportId: "R-2", reportType: "weekly", title: "Roundup" })).status).toBe("submitted");
      expect((await submitReport(e, { reportId: "R-X", reportType: "x", title: "y", entityId: "GHOST" })).status).toBe("entityNotFound");
      expect((await publishReport(e, { reportId: "R-1" })).newStatus).toBe("published");
      expect((await publishReport(e, { reportId: "R-1" })).status).toBe("rejected"); // already published
      expect((await listReports(e, { status: "published" })).total).toBe(1);
    });
    it("coverage rolls up the three collections", async () => {
      await recordEvent(e, { eventId: "EV-1", entityId: "EN-1", eventType: "mention", occurredAt: "2026-06-01T00:00:00Z" });
      await submitReport(e, { reportId: "R-1", reportType: "summary", title: "Brief", entityId: "EN-1" });
      const cov = await coverage(e);
      expect(cov.entityCount).toBe(1);
      expect(cov.eventCount).toBe(1);
      expect(cov.reportCount).toBe(1);
      expect(cov.entitiesByKind?.org).toBe(1);
      expect(cov.reportsByStatus?.draft).toBe(1);
    });
  });
});
