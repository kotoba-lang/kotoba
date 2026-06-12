-- SQLMesh model: mv_copyright_ingest_latest
-- Latest ingest run summary per registry (crossref / datacite).
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_copyright_ingest_run
--   → mv_copyright_ingest_latest

MODEL (
  name dev.mv_copyright_ingest_latest,
  kind FULL,
  dialect postgres,
  description 'Latest ingest run summary per registry (crossref / datacite).',
  grain [registry],
  tags [copyright, ingest, coverage, materialized_view]
);

SELECT
  registry,
  COUNT(*)              AS run_count,
  SUM(rows_inserted)    AS total_rows_inserted,
  MAX(started_at)       AS last_started_at,
  MAX(finished_at)      AS last_finished_at
FROM vertex_copyright_ingest_run
GROUP BY registry
