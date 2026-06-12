-- Open smartphone layer KPI: per-(layer, activity) execution metrics from supply chain trace.
MODEL (
  name dev.mv_open_smartphone_layer_kpi,
  kind FULL,
  dialect postgres,
  description 'Per (layer, activity): exec count, avg/max duration, error/success counts.',
  grain [layer, activity],
  tags [open_smartphone, layer, kpi]
);

SELECT
  layer,
  activity,
  COUNT(*) AS exec_count,
  AVG(duration_ms)::BIGINT AS avg_duration_ms,
  MAX(duration_ms) AS max_duration_ms,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
  SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS success_count
FROM dev.mv_open_smartphone_supply_chain_trace
WHERE duration_ms IS NOT NULL
GROUP BY layer, activity
