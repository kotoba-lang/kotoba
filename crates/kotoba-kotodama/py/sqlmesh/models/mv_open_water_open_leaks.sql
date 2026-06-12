-- Open water open leaks: active leak summary per water main.
MODEL (
  name dev.mv_open_water_open_leaks,
  kind FULL,
  dialect postgres,
  description 'Per main_vertex_id: open leak count, worst severity, public notice flag, latest reported.',
  grain [main_vertex_id],
  tags [open_water, leak, severity, infrastructure]
);

SELECT
  main_vertex_id,
  COUNT(*) AS open_leak_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_water_leak
WHERE status = 'open'
GROUP BY main_vertex_id
