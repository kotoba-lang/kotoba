-- Mangaka process KPI: execution stats per BPMN activity.
MODEL (
  name dev.mv_mangaka_process_kpi,
  kind FULL,
  dialect postgres,
  description 'Per activity: execution count, avg/max/min duration, error count, partial count.',
  grain [activity],
  tags [mangaka, process, kpi, bpmn]
);

SELECT
  activity,
  COUNT(*) AS exec_count,
  AVG(duration_ms)::BIGINT AS avg_duration_ms,
  MAX(duration_ms) AS max_duration_ms,
  MIN(duration_ms) AS min_duration_ms,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
  SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) AS partial_count
FROM mv_mangaka_process_trace
WHERE duration_ms IS NOT NULL
GROUP BY activity
