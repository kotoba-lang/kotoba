-- ADR-2605080500: SQLMesh Phase 0 source-of-truth for mv_shosha_sanctions_count_by_source
-- Active sanctions entry counts by source (OFAC / UN-1267 / etc.) and entity type.
MODEL (
  name dev.mv_shosha_sanctions_count_by_source,
  kind FULL,
  dialect postgres,
  description 'Active sanctions entry count by list_source and entity_type.',
  grain [list_source, entity_type],
  tags [shosha, sanctions, compliance, materialized_view, adr_2605080500]
);

SELECT
  list_source,
  entity_type,
  COUNT(*) AS active_count
FROM vertex_shosha_sanctions_list
WHERE status = 'active'
GROUP BY list_source, entity_type
