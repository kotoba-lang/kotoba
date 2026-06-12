-- Zeebe incident summary: incident created and resolved counts per process.
MODEL (
  name dev.mv_zeebe_incident_summary,
  kind FULL,
  dialect postgres,
  description 'Per process_id: incident created and resolved counts from Zeebe audit log.',
  grain [process_id],
  tags [zeebe, bpmn, incident, summary]
);

SELECT
  process_id,
  SUM(CASE WHEN intent = 'CREATED' THEN 1 ELSE 0 END) AS created_count,
  SUM(CASE WHEN intent = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_count,
  COUNT(*) AS total_incidents
FROM vertex_zeebe_audit_log
WHERE element_type = 'INCIDENT'
GROUP BY process_id
