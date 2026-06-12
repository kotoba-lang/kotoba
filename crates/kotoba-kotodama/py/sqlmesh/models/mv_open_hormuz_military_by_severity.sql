-- Open Hormuz military incidents by severity: confirmed incidents per aggressor and severity.
MODEL (
  name dev.mv_open_hormuz_military_by_severity,
  kind FULL,
  dialect postgres,
  description 'Per (aggressor_party, severity): incident count, vessel seizure flag, latest occurred.',
  grain [aggressor_party, severity],
  tags [open_hormuz, military, incident]
);

SELECT
  aggressor_party,
  severity,
  COUNT(*) AS incident_count,
  BOOL_OR(vessel_seized) AS any_seizure,
  MAX(occurred_at) AS latest_occurred
FROM vertex_open_hormuz_military_incident
WHERE status = 'confirmed'
GROUP BY aggressor_party, severity
