-- OSM ingest recent: ingest run history ordered by start time.
MODEL (
  name dev.mv_osm_ingest_recent,
  kind FULL,
  dialect postgres,
  description 'OSM ingest runs ordered by started_at DESC: phase, status, throughput, completion.',
  grain [run_id],
  tags [osm, ingest, run]
);

SELECT
  run_id,
  source_did,
  phase,
  status,
  nodes_written,
  ways_written,
  rows_per_sec,
  started_at,
  completed_at
FROM vertex_osm_ingest_run
ORDER BY started_at DESC
