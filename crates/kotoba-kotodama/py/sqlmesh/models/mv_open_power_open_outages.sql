-- Open power outages: per-feeder open outage summary.
MODEL (
  name dev.mv_open_power_open_outages,
  kind FULL,
  dialect postgres,
  description 'Per feeder_vertex_id: open outage count, worst severity, public notice flag, customers affected, latest report.',
  grain [feeder_vertex_id],
  tags [open_power, outage, open]
);

SELECT
  feeder_vertex_id,
  COUNT(*) AS open_outage_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  SUM(customers_affected) AS total_customers_affected,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_power_outage
WHERE status = 'open'
GROUP BY feeder_vertex_id
