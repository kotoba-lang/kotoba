-- Mangaka process case summary: phase counts and status per case.
MODEL (
  name dev.mv_mangaka_process_case_summary,
  kind FULL,
  dialect postgres,
  description 'Per case_id: phase count, total duration, error count, last event timestamp, and inferred status.',
  grain [case_id],
  tags [mangaka, process, case, summary]
);

SELECT
  case_id,
  COUNT(*) AS phase_count,
  SUM(duration_ms) AS total_duration_ms,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
  MAX(timestamp) AS last_event_at,
  CASE
    WHEN MAX(activity) = 'mangaka.episodePublished' THEN 'complete'
    WHEN SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) > 0 THEN 'failed'
    ELSE 'running'
  END AS status
FROM mv_mangaka_process_trace
GROUP BY case_id
