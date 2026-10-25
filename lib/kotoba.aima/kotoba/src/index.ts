/**
 * aima kotoba — barrel.
 *
 * Per ADR-2606011400. The aima knowledge-graph data layer on the etzhayyim
 * substrate (AT PDS records; no RW).
 *
 *   entity : defineEntity / getEntity / listEntities (q = app-layer search) / archiveEntity
 *   event  : recordEvent (FK→entity) / listEvents
 *   report : submitReport (optional FK→entity) / publishReport / listReports
 *   coverage
 *
 * The embedding/inference/mesh AI-compute components stay etzhayyim infra.
 */

export * from "./types.js";
export {
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
} from "./registry.js";
