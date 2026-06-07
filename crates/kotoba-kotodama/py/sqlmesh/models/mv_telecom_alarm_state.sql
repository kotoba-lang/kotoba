-- Telecom alarm state: alarm counts per source/severity/status.
MODEL (
  name dev.mv_telecom_alarm_state,
  kind FULL,
  dialect postgres,
  description 'Per (source_kind, severity, status): alarm count from vertex_telecom_alarm.',
  grain [source_kind, severity, status],
  tags [telecom, alarm, state]
);

SELECT
  source_kind,
  severity,
  status,
  COUNT(*) AS alarm_count
FROM vertex_telecom_alarm
GROUP BY source_kind, severity, status
