-- Open airplane open incidents: per-aircraft active incident summary.
MODEL (
  name dev.mv_open_airplane_open_incidents,
  kind FULL,
  dialect postgres,
  description 'Per aircraft_vid: open incident count, worst severity, public notice flag, and latest report.',
  grain [aircraft_vid],
  tags [open_airplane, incident, open]
);

SELECT
  aircraft_vid,
  COUNT(*) AS open_incident_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_airplane_incident
WHERE status = 'open'
GROUP BY aircraft_vid
