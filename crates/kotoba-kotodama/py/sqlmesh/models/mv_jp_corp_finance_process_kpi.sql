-- JP corp finance process KPI: activity-level execution metrics from process trace.
MODEL (
  name dev.mv_jp_corp_finance_process_kpi,
  kind FULL,
  dialect postgres,
  description 'Per (activity, source_id): execution count, avg/max duration, error/success counts and record totals.',
  grain [activity, source_id],
  tags [jp, corp_finance, process, kpi]
);

SELECT
  activity,
  source_id,
  COUNT(*) AS exec_count,
  AVG(duration_ms)::BIGINT AS avg_duration_ms,
  MAX(duration_ms) AS max_duration_ms,
  SUM(CASE WHEN status IN ('error', 'failed') THEN 1 ELSE 0 END) AS error_count,
  SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS success_count,
  SUM(COALESCE(records_prepared, 0)) AS records_prepared,
  SUM(COALESCE(records_written, 0)) AS records_written,
  SUM(COALESCE(records_visible, 0)) AS records_visible,
  SUM(COALESCE(invalid_count, 0)) AS invalid_count
FROM dev.mv_jp_corp_finance_process_trace
GROUP BY activity, source_id
