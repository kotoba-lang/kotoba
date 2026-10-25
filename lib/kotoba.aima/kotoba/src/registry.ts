/**
 * aima kotoba — entity + event + report knowledge-graph registries + coverage.
 * AT PDS records (no RW). Events FK-reference an existing entity; reports may
 * optionally FK-reference one. Public graph data only.
 */

import type { Etzhayyim } from "@etzhayyim/sdk";
import {
  ENTITY_COLLECTION,
  EVENT_COLLECTION,
  REPORT_COLLECTION,
  entityDidFor,
  entityRkey,
  eventDidFor,
  eventRkey,
  reportDidFor,
  reportRkey,
  type ArchiveEntityInput,
  type ArchiveEntityOutput,
  type CoverageInput,
  type CoverageOutput,
  type DefineEntityInput,
  type DefineEntityOutput,
  type EntityRecord,
  type EntityView,
  type EventRecord,
  type EventView,
  type GetEntityInput,
  type GetEntityOutput,
  type ListEntitiesInput,
  type ListEntitiesOutput,
  type ListEventsInput,
  type ListEventsOutput,
  type ListReportsInput,
  type ListReportsOutput,
  type PublishReportInput,
  type PublishReportOutput,
  type RecordEventInput,
  type RecordEventOutput,
  type ReportRecord,
  type ReportView,
  type SubmitReportInput,
  type SubmitReportOutput,
} from "./types.js";

const PAGE_LIMIT = 100;
const DEFAULT_MAX_SCAN = 10_000;

async function exists(e: Etzhayyim, collection: string, rkey: string): Promise<boolean> {
  const resp = await e.read({ collection, rkey }).catch(() => ({ records: [] }));
  return Boolean(resp.records[0]?.value);
}

// ─── Entity ─────────────────────────────────────────────────────────

export async function defineEntity(e: Etzhayyim, input: DefineEntityInput): Promise<DefineEntityOutput> {
  if (!input.entityId || !input.name || !input.kind) return { status: "rejected", error: "missingRequiredFields" };
  const rkey = entityRkey(input.entityId);
  const existing = await e.read<EntityRecord>({ collection: ENTITY_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", entityUri: existing.records[0].uri, did: existing.records[0].value.did, entityId: input.entityId };
  }
  const did = entityDidFor(input.entityId);
  const record: EntityRecord = {
    did,
    entityId: input.entityId,
    name: input.name,
    kind: input.kind,
    category: input.category,
    status: "active",
    createdAt: new Date().toISOString(),
  };
  const receipt = await e.write({ collection: ENTITY_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "defined", entityUri: receipt.uri, did, entityId: input.entityId };
}

export async function getEntity(e: Etzhayyim, input: GetEntityInput): Promise<GetEntityOutput> {
  if (!input.entityId) return { error: "invalidEntityId" };
  const resp = await e.read<EntityRecord>({ collection: ENTITY_COLLECTION, rkey: entityRkey(input.entityId) }).catch(() => ({ records: [] }));
  const r = resp.records[0];
  if (!r) return { error: "notFound" };
  return { entity: { ...r.value, entityUri: r.uri } };
}

export async function listEntities(e: Etzhayyim, input: ListEntitiesInput = {}): Promise<ListEntitiesOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<EntityRecord>({ collection: ENTITY_COLLECTION, cursor: input.cursor, limit });
  const q = input.q?.toLowerCase();
  const items: EntityView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.kind && v.kind !== input.kind) return false;
      if (input.category && v.category !== input.category) return false;
      if (input.status && v.status !== input.status) return false;
      if (q && !v.name.toLowerCase().includes(q)) return false;
      return true;
    })
    .map((r) => ({ ...r.value, entityUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

export async function archiveEntity(e: Etzhayyim, input: ArchiveEntityInput): Promise<ArchiveEntityOutput> {
  if (!input.entityId) return { status: "rejected", error: "invalidEntityId" };
  const rkey = entityRkey(input.entityId);
  const resp = await e.read<EntityRecord>({ collection: ENTITY_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const ent = resp.records[0]?.value;
  if (!ent) return { status: "notFound", error: "entityNotFound" };
  if (ent.status === "archived") return { status: "rejected", error: "alreadyArchived" };
  await e.write({ collection: ENTITY_COLLECTION, record: { ...ent, status: "archived" } as unknown as Record<string, unknown>, rkey });
  return { status: "archived", entityId: input.entityId };
}

// ─── Event ──────────────────────────────────────────────────────────

export async function recordEvent(e: Etzhayyim, input: RecordEventInput): Promise<RecordEventOutput> {
  if (!input.eventId || !input.entityId || !input.eventType || !input.occurredAt) {
    return { status: "rejected", error: "missingRequiredFields" };
  }
  if (!(await exists(e, ENTITY_COLLECTION, entityRkey(input.entityId)))) {
    return { status: "entityNotFound", error: `entityNotFound:${input.entityId}` };
  }
  const rkey = eventRkey(input.eventId);
  const existing = await e.read<EventRecord>({ collection: EVENT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", eventUri: existing.records[0].uri, did: existing.records[0].value.did, eventId: input.eventId };
  }
  const did = eventDidFor(input.eventId);
  const record: EventRecord = {
    did,
    eventId: input.eventId,
    entityId: input.entityId,
    eventType: input.eventType,
    occurredAt: input.occurredAt,
    summary: input.summary,
    createdAt: new Date().toISOString(),
  };
  const receipt = await e.write({ collection: EVENT_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "recorded", eventUri: receipt.uri, did, eventId: input.eventId };
}

export async function listEvents(e: Etzhayyim, input: ListEventsInput = {}): Promise<ListEventsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<EventRecord>({ collection: EVENT_COLLECTION, cursor: input.cursor, limit });
  const items: EventView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.entityId && v.entityId !== input.entityId) return false;
      if (input.eventType && v.eventType !== input.eventType) return false;
      if (input.since && v.occurredAt < input.since) return false;
      return true;
    })
    .map((r) => ({ ...r.value, eventUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Report ─────────────────────────────────────────────────────────

export async function submitReport(e: Etzhayyim, input: SubmitReportInput): Promise<SubmitReportOutput> {
  if (!input.reportId || !input.reportType || !input.title) return { status: "rejected", error: "missingRequiredFields" };
  if (input.entityId && !(await exists(e, ENTITY_COLLECTION, entityRkey(input.entityId)))) {
    return { status: "entityNotFound", error: `entityNotFound:${input.entityId}` };
  }
  const rkey = reportRkey(input.reportId);
  const existing = await e.read<ReportRecord>({ collection: REPORT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  if (existing.records[0]?.value) {
    return { status: "alreadyExists", reportUri: existing.records[0].uri, did: existing.records[0].value.did, reportId: input.reportId };
  }
  const did = reportDidFor(input.reportId);
  const record: ReportRecord = {
    did,
    reportId: input.reportId,
    entityId: input.entityId,
    reportType: input.reportType,
    title: input.title,
    summary: input.summary,
    status: "draft",
    createdAt: new Date().toISOString(),
  };
  const receipt = await e.write({ collection: REPORT_COLLECTION, record: record as unknown as Record<string, unknown>, rkey });
  return { status: "submitted", reportUri: receipt.uri, did, reportId: input.reportId };
}

export async function publishReport(e: Etzhayyim, input: PublishReportInput): Promise<PublishReportOutput> {
  if (!input.reportId) return { status: "rejected", error: "invalidReportId" };
  const rkey = reportRkey(input.reportId);
  const resp = await e.read<ReportRecord>({ collection: REPORT_COLLECTION, rkey }).catch(() => ({ records: [] }));
  const rep = resp.records[0]?.value;
  if (!rep) return { status: "notFound", error: "reportNotFound" };
  if (rep.status === "published") return { status: "rejected", error: "alreadyPublished" };
  await e.write({ collection: REPORT_COLLECTION, record: { ...rep, status: "published" } as unknown as Record<string, unknown>, rkey });
  return { status: "published", reportId: input.reportId, newStatus: "published" };
}

export async function listReports(e: Etzhayyim, input: ListReportsInput = {}): Promise<ListReportsOutput> {
  const limit = Math.min(input.limit ?? 50, 200);
  const resp = await e.read<ReportRecord>({ collection: REPORT_COLLECTION, cursor: input.cursor, limit });
  const items: ReportView[] = resp.records
    .filter((r) => {
      const v = r.value;
      if (input.entityId && v.entityId !== input.entityId) return false;
      if (input.reportType && v.reportType !== input.reportType) return false;
      if (input.status && v.status !== input.status) return false;
      return true;
    })
    .map((r) => ({ ...r.value, reportUri: r.uri }));
  return { items, cursor: resp.cursor, total: items.length };
}

// ─── Coverage ───────────────────────────────────────────────────────

async function countAll<T>(e: Etzhayyim, collection: string, maxScan: number, onRow: (v: T) => void): Promise<number> {
  let cursor: string | undefined;
  let scanned = 0;
  while (scanned < maxScan) {
    const page = await e.read<T>({ collection, cursor, limit: PAGE_LIMIT });
    for (const r of page.records) {
      if (scanned >= maxScan) break;
      onRow(r.value);
      scanned += 1;
    }
    if (scanned >= maxScan || !page.cursor || page.records.length < PAGE_LIMIT) break;
    cursor = page.cursor;
  }
  return scanned;
}

export async function coverage(e: Etzhayyim, input: CoverageInput = {}): Promise<CoverageOutput> {
  const maxScan = Math.min(input.maxScan ?? DEFAULT_MAX_SCAN, DEFAULT_MAX_SCAN);
  const entitiesByKind: Record<string, number> = {};
  const entityCount = await countAll<EntityRecord>(e, ENTITY_COLLECTION, maxScan, (v) => {
    entitiesByKind[v.kind] = (entitiesByKind[v.kind] ?? 0) + 1;
  });
  const eventCount = await countAll<EventRecord>(e, EVENT_COLLECTION, maxScan, () => {});
  const reportsByStatus: Record<string, number> = {};
  const reportCount = await countAll<ReportRecord>(e, REPORT_COLLECTION, maxScan, (v) => {
    reportsByStatus[v.status] = (reportsByStatus[v.status] ?? 0) + 1;
  });
  return {
    entityCount,
    eventCount,
    reportCount,
    entitiesByKind,
    reportsByStatus,
    truncated: entityCount >= maxScan || eventCount >= maxScan || reportCount >= maxScan,
  };
}
