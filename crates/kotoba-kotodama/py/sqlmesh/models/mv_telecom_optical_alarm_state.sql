-- Telecom optical alarm state: optical alarm counts per source/kind/severity/status.
MODEL (
  name dev.mv_telecom_optical_alarm_state,
  kind FULL,
  dialect postgres,
  description 'Per (source_kind, alarm_kind, severity, status): optical alarm count.',
  grain [source_kind, alarm_kind, severity, status],
  tags [telecom, optical, alarm]
);

SELECT
  source_kind,
  alarm_kind,
  severity,
  status,
  COUNT(*) AS alarm_count
FROM vertex_telecom_optical_alarm
GROUP BY source_kind, alarm_kind, severity, status
