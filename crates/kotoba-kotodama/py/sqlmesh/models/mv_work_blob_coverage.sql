-- SQLMesh model: mv_work_blob_coverage
-- Coverage of open-access full text by license and status (ADR-2605080500).
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_work_blob
--   → mv_work_blob_coverage

MODEL (
  name dev.mv_work_blob_coverage,
  kind FULL,
  dialect postgres,
  description 'Coverage of open-access full text by license and status.',
  grain [license, status],
  tags [copyright, fulltext, coverage, materialized_view]
);

SELECT
  license,
  status,
  COUNT(*)              AS cnt,
  AVG(LENGTH(fulltext)) AS avg_text_bytes
FROM vertex_work_blob
GROUP BY license, status
