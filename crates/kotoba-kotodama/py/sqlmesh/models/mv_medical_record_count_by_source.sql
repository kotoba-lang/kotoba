-- Medical record count by source: source-record edge counts per (source_id, collection).
MODEL (
  name dev.mv_medical_record_count_by_source,
  kind FULL,
  dialect postgres,
  description 'Per (source_id, collection): record count and latest updated_at from edge_medical_source_record.',
  grain [source_id, collection],
  tags [medical, source, record]
);

SELECT
  source_id,
  collection,
  COUNT(*)::BIGINT AS record_count,
  MAX(updated_at) AS latest_linked_at
FROM edge_medical_source_record
GROUP BY source_id, collection
