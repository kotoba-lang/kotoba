-- Docs entity activity: event count and last event per entity.
MODEL (
  name dev.mv_docs_entity_activity,
  kind FULL,
  dialect postgres,
  description 'Per entity_id: event count, last event timestamp, and last seq from vertex_docs_event.',
  grain [entity_id],
  tags [docs, entity, activity, events]
);

SELECT
  e.entity_id,
  COUNT(*) AS event_count,
  MAX(e.occurred_at) AS last_event_at,
  MAX(e._seq) AS last_seq
FROM vertex_docs_event e
WHERE e.entity_id IS NOT NULL
GROUP BY e.entity_id
