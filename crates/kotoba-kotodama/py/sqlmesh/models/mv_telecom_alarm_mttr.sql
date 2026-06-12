-- Telecom alarm MTTR: cleared alarm mean time to resolution per source/severity.
MODEL (
  name dev.mv_telecom_alarm_mttr,
  kind FULL,
  dialect postgres,
  description 'Per (source_kind, severity): avg/min/max MTTR seconds and cleared count.',
  grain [source_kind, severity],
  tags [telecom, alarm, mttr]
);

SELECT
  source_kind,
  severity,
  AVG(mttr_seconds) AS avg_mttr_seconds,
  MIN(mttr_seconds) AS min_mttr_seconds,
  MAX(mttr_seconds) AS max_mttr_seconds,
  COUNT(*) AS cleared_count
FROM vertex_telecom_alarm
WHERE status = 'cleared' AND mttr_seconds IS NOT NULL
GROUP BY source_kind, severity
