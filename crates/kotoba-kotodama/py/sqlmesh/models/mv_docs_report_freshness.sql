-- Docs report freshness: report count and last update per entity.
MODEL (
  name dev.mv_docs_report_freshness,
  kind FULL,
  dialect postgres,
  description 'Per entity_id: report count, last report timestamp, and last seq from vertex_docs_report.',
  grain [entity_id],
  tags [docs, report, freshness, entity]
);

SELECT
  r.entity_id,
  COUNT(*) AS report_count,
  MAX(r.updated_at) AS last_report_at,
  MAX(r._seq) AS last_seq
FROM vertex_docs_report r
WHERE r.entity_id IS NOT NULL
GROUP BY r.entity_id
