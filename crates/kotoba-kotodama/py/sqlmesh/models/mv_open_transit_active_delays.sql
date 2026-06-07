-- Open transit active delays: per-route active delay summary.
MODEL (
  name dev.mv_open_transit_active_delays,
  kind FULL,
  dialect postgres,
  description 'Per route_vertex_id: active delay count, worst severity, public notice flag, max delay, latest report.',
  grain [route_vertex_id],
  tags [open_transit, delay, active]
);

SELECT
  route_vertex_id,
  COUNT(*) AS active_delay_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(delay_minutes) AS max_delay_minutes,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_transit_delay
WHERE status = 'active'
GROUP BY route_vertex_id
