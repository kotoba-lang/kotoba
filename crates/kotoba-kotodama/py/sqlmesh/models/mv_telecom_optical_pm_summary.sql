-- Telecom optical PM summary: optical performance monitoring event aggregates.
MODEL (
  name dev.mv_telecom_optical_pm_summary,
  kind FULL,
  dialect postgres,
  description 'Per (source_kind, metric, breach): event count, avg/min/max value.',
  grain [source_kind, metric, breach],
  tags [telecom, optical, pm, summary]
);

SELECT
  source_kind,
  metric,
  breach,
  COUNT(*) AS event_count,
  AVG(value) AS avg_value,
  MIN(value) AS min_value,
  MAX(value) AS max_value
FROM vertex_telecom_optical_pm_event
GROUP BY source_kind, metric, breach
