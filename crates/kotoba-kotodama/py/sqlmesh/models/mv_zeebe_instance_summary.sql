-- Zeebe instance summary: BPMN process instance counts by intent and state.
MODEL (
  name dev.mv_zeebe_instance_summary,
  kind FULL,
  dialect postgres,
  description 'Per process_id: activating, completing, and terminating counts from Zeebe audit log.',
  grain [process_id],
  tags [zeebe, bpmn, instance, summary]
);

SELECT
  process_id,
  SUM(CASE WHEN intent = 'ELEMENT_ACTIVATING' THEN 1 ELSE 0 END) AS activating_count,
  SUM(CASE WHEN intent = 'ELEMENT_COMPLETING' THEN 1 ELSE 0 END) AS completing_count,
  SUM(CASE WHEN intent = 'ELEMENT_TERMINATING' THEN 1 ELSE 0 END) AS terminating_count,
  COUNT(*) AS total_events
FROM vertex_zeebe_audit_log
WHERE element_type = 'PROCESS'
GROUP BY process_id
