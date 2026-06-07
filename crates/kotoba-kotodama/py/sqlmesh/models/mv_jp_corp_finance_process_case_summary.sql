-- JP corp finance process case summary: per-case event aggregates from process trace.
MODEL (
  name dev.mv_jp_corp_finance_process_case_summary,
  kind FULL,
  dialect postgres,
  description 'Per case_id: event count, timestamps, record totals, and derived status.',
  grain [case_id],
  tags [jp, corp_finance, process, case, summary]
);

SELECT
  case_id,
  COUNT(*) AS event_count,
  MIN(timestamp) AS first_event_at,
  MAX(timestamp) AS last_event_at,
  MAX(source_id) AS source_id,
  MAX(target_date) AS target_date,
  MAX(jcn) AS jcn,
  MAX(edinet_code) AS edinet_code,
  SUM(COALESCE(records_prepared, 0)) AS records_prepared,
  SUM(COALESCE(records_written, 0)) AS records_written,
  SUM(COALESCE(records_visible, 0)) AS records_visible,
  SUM(COALESCE(invalid_count, 0)) AS invalid_count,
  CASE
    WHEN SUM(CASE WHEN status IN ('error', 'failed') THEN 1 ELSE 0 END) > 0 THEN 'failed'
    WHEN MAX(activity) LIKE 'jpCorpFinance.%.completed' THEN 'complete'
    ELSE 'running'
  END AS status
FROM dev.mv_jp_corp_finance_process_trace
GROUP BY case_id
