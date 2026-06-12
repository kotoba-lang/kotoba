-- Kotodama organizer run health: per-status run aggregates.
MODEL (
  name dev.mv_kotodama_organizer_run_health,
  kind FULL,
  dialect postgres,
  description 'Per status: run count, latest indexed_at, avg fleet_saturation, avg latency_ms.',
  grain [status],
  tags [kotodama, organizer, run, health]
);

SELECT
  status,
  COUNT(*) AS run_count,
  MAX(indexed_at) AS latest_indexed_at,
  AVG(fleet_saturation) AS avg_fleet_saturation,
  AVG(latency_ms) AS avg_latency_ms
FROM vertex_kotodama_organizer_run
GROUP BY status
