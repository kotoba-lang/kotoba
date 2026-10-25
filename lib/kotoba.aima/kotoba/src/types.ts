/**
 * aima kotoba — knowledge-graph data-layer record types.
 *
 * Per ADR-2606011400. aima is an AI-agent platform; its SUBSTRATE DATA LAYER is
 * a generic knowledge graph: entities + events (FK→entity) + reports (FK→entity,
 * optional). Registry on AT PDS records (replaces the RisingWave/Postgres backing
 * named in MIGRATION-TODO). ADR-2605172000 kotoba.
 *
 * SPLIT NOTE: the embedding / inference / mesh AI-compute components
 * (etzhayyim-wasm-laser / -inference / -mesh) stay etzhayyim infra, invoked via
 * consent-capability; only the entity/event/report graph is etzhayyim-front.
 *
 * AXIS NOTE (ADR-2605172400): axis-clean — AT records are public by design; no
 * PII custody (generic name/kind/category/status attributes), no settlement
 * (KPI "credits" is internal scoring), no fulfillment liability. PII MUST NOT be
 * written to these public records (per root rules).
 *
 * Identity hierarchy:
 *   did:web:aima.etzhayyim.com                       — controller
 *   did:web:aima.etzhayyim.com:entity:{entityId}     — a graph entity
 *   did:web:aima.etzhayyim.com:event:{eventId}       — an event
 *   did:web:aima.etzhayyim.com:report:{reportId}     — a report
 */

export const AIMA_DID_PREFIX = "did:web:aima.etzhayyim.com:" as const;

export const ENTITY_COLLECTION = "com.etzhayyim.apps.aima.aimaEntity";
export const EVENT_COLLECTION = "com.etzhayyim.apps.aima.aimaEvent";
export const REPORT_COLLECTION = "com.etzhayyim.apps.aima.aimaReport";

// ─── Entity ─────────────────────────────────────────────────────────

export type EntityStatus = "active" | "archived";

export interface EntityRecord {
  did: string;
  entityId: string;
  name: string;
  /** Free-form node kind (e.g. "org", "topic", "service"). */
  kind: string;
  category?: string;
  status: EntityStatus;
  createdAt: string;
}
export interface EntityView extends EntityRecord {
  entityUri: string;
}
export interface DefineEntityInput {
  entityId: string;
  name: string;
  kind: string;
  category?: string;
}
export interface DefineEntityOutput {
  status: "defined" | "alreadyExists" | "rejected";
  entityUri?: string;
  did?: string;
  entityId?: string;
  error?: string;
}
export interface GetEntityInput {
  entityId: string;
}
export interface GetEntityOutput {
  entity?: EntityView;
  error?: string;
}
export interface ListEntitiesInput {
  kind?: string;
  category?: string;
  status?: EntityStatus;
  /** App-layer substring match over name (AT PDS has no text search). */
  q?: string;
  limit?: number;
  cursor?: string;
}
export interface ListEntitiesOutput {
  items: EntityView[];
  cursor?: string;
  total: number;
}
export interface ArchiveEntityInput {
  entityId: string;
}
export interface ArchiveEntityOutput {
  status: "archived" | "notFound" | "rejected";
  entityId?: string;
  error?: string;
}

// ─── Event ──────────────────────────────────────────────────────────

export interface EventRecord {
  did: string;
  eventId: string;
  /** FK → entity entityId. */
  entityId: string;
  eventType: string;
  occurredAt: string;
  summary?: string;
  createdAt: string;
}
export interface EventView extends EventRecord {
  eventUri: string;
}
export interface RecordEventInput {
  eventId: string;
  entityId: string;
  eventType: string;
  occurredAt: string;
  summary?: string;
}
export interface RecordEventOutput {
  status: "recorded" | "alreadyExists" | "rejected" | "entityNotFound";
  eventUri?: string;
  did?: string;
  eventId?: string;
  error?: string;
}
export interface ListEventsInput {
  entityId?: string;
  eventType?: string;
  since?: string;
  limit?: number;
  cursor?: string;
}
export interface ListEventsOutput {
  items: EventView[];
  cursor?: string;
  total: number;
}

// ─── Report ─────────────────────────────────────────────────────────

export type ReportStatus = "draft" | "published";

export interface ReportRecord {
  did: string;
  reportId: string;
  /** FK → entity entityId (optional — a report may be cross-entity). */
  entityId?: string;
  reportType: string;
  title: string;
  summary?: string;
  status: ReportStatus;
  createdAt: string;
}
export interface ReportView extends ReportRecord {
  reportUri: string;
}
export interface SubmitReportInput {
  reportId: string;
  reportType: string;
  title: string;
  entityId?: string;
  summary?: string;
}
export interface SubmitReportOutput {
  status: "submitted" | "alreadyExists" | "rejected" | "entityNotFound";
  reportUri?: string;
  did?: string;
  reportId?: string;
  error?: string;
}
export interface PublishReportInput {
  reportId: string;
}
export interface PublishReportOutput {
  status: "published" | "notFound" | "rejected";
  reportId?: string;
  newStatus?: ReportStatus;
  error?: string;
}
export interface ListReportsInput {
  entityId?: string;
  reportType?: string;
  status?: ReportStatus;
  limit?: number;
  cursor?: string;
}
export interface ListReportsOutput {
  items: ReportView[];
  cursor?: string;
  total: number;
}

// ─── Coverage ───────────────────────────────────────────────────────

export interface CoverageInput {
  maxScan?: number;
}
export interface CoverageOutput {
  entityCount?: number;
  eventCount?: number;
  reportCount?: number;
  entitiesByKind?: Record<string, number>;
  reportsByStatus?: Record<string, number>;
  truncated?: boolean;
  error?: string;
}

// ─── Helpers ────────────────────────────────────────────────────────

export function entityDidFor(id: string): string {
  return `${AIMA_DID_PREFIX}entity:${id.toLowerCase()}`;
}
export function entityRkey(id: string): string {
  return `entity-${id.toLowerCase()}`;
}
export function eventDidFor(id: string): string {
  return `${AIMA_DID_PREFIX}event:${id.toLowerCase()}`;
}
export function eventRkey(id: string): string {
  return `event-${id.toLowerCase()}`;
}
export function reportDidFor(id: string): string {
  return `${AIMA_DID_PREFIX}report:${id.toLowerCase()}`;
}
export function reportRkey(id: string): string {
  return `report-${id.toLowerCase()}`;
}
