-- Open ports open incidents: active incident summary per port.
MODEL (
  name dev.mv_open_ports_open_incidents,
  kind FULL,
  dialect postgres,
  description 'Per port_vid: open incident count, worst severity, public notice flag, latest reported.',
  grain [port_vid],
  tags [open_ports, incident, severity, maritime]
);

SELECT
  port_vid,
  COUNT(*) AS open_incident_count,
  MAX(severity) AS worst_severity,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(reported_at) AS latest_reported_at
FROM vertex_open_ports_incident
WHERE status = 'open'
GROUP BY port_vid
