-- SQLMesh model: mv_copyright_work_coverage
-- Per-registry work coverage: total works, works with blob, works with fulltext.
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_work
--   vertex_work_blob
--   → mv_copyright_work_coverage

MODEL (
  name dev.mv_copyright_work_coverage,
  kind FULL,
  dialect postgres,
  description 'Per-registry work coverage: total works, works with blob, works with fulltext.',
  grain [registry],
  tags [copyright, fulltext, coverage, materialized_view]
);

SELECT
  w.registry,
  COUNT(*)                                            AS total_works,
  COUNT(wb.work_vertex_id)                            AS works_with_blob,
  COUNT(CASE WHEN wb.fulltext IS NOT NULL THEN 1 END) AS works_with_fulltext
FROM vertex_work w
LEFT JOIN vertex_work_blob wb ON wb.work_vertex_id = w.vertex_id
GROUP BY w.registry
