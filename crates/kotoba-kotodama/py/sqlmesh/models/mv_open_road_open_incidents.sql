-- Open road open incidents: per-road active incident summary.
MODEL (
  name dev.mv_open_road_open_incidents,
  kind FULL,
  dialect postgres,
  description 'Per road_vertex_id: open incident count, worst severity, public notice flag, total delay, latest report.',
  grain [road_vertex_id],
  tags [open_road, incident, open]
);

SELECT
  road_vertex_id,
  COUNT(*) AS open_incident_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  SUM(estimated_delay_minutes) AS total_delay_minutes,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_road_incident
WHERE status = 'open'
GROUP BY road_vertex_id
