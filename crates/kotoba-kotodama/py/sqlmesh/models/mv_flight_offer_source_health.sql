-- Flight offer source health: run statistics per offer source.
MODEL (
  name dev.mv_flight_offer_source_health,
  kind FULL,
  dialect postgres,
  description 'Per source_id: run counts by status (ok/error/fallback), avg latency, total offers written, and last run timestamps.',
  grain [source_id],
  tags [flight, offer, source, health, monitoring]
);

SELECT
  source_id,
  COUNT(*)::BIGINT AS runs_total,
  SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END)::BIGINT AS runs_ok,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)::BIGINT AS runs_error,
  SUM(CASE WHEN status = 'fallback' THEN 1 ELSE 0 END)::BIGINT AS runs_fallback,
  AVG(latency_ms)::DOUBLE PRECISION AS avg_latency_ms,
  SUM(offers_written)::BIGINT AS offers_written_total,
  MAX(observed_at) AS last_run_at,
  MAX(CASE WHEN status = 'ok' THEN observed_at ELSE NULL END) AS last_ok_at
FROM vertex_flight_offer_source_run
GROUP BY source_id
