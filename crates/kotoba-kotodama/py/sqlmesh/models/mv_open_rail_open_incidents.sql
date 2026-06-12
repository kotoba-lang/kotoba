-- Open rail open incidents: per-line active rail incident summary.
MODEL (
  name dev.mv_open_rail_open_incidents,
  kind FULL,
  dialect postgres,
  description 'Per line_vid: open incident count, worst severity, public notice flag, total delay, latest report.',
  grain [line_vid],
  tags [open_rail, incident, open]
);

SELECT
  line_vid,
  COUNT(*) AS open_incident_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  SUM(delay_minutes) AS total_delay_minutes,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_rail_incident
WHERE status = 'open'
GROUP BY line_vid
