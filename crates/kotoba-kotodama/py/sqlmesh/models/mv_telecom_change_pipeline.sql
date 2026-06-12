-- Telecom change pipeline: change request counts per kind/risk/status.
MODEL (
  name dev.mv_telecom_change_pipeline,
  kind FULL,
  dialect postgres,
  description 'Per (change_kind, risk_level, status): change request count.',
  grain [change_kind, risk_level, status],
  tags [telecom, change, pipeline]
);

SELECT
  change_kind,
  risk_level,
  status,
  COUNT(*) AS change_count
FROM vertex_telecom_change_request
GROUP BY change_kind, risk_level, status
