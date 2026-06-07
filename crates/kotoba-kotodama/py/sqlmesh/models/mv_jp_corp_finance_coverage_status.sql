-- JP corp finance coverage status: company counts per coverage status and missing reason.
MODEL (
  name dev.mv_jp_corp_finance_coverage_status,
  kind FULL,
  dialect postgres,
  description 'Per (coverage_status, missing_reason): company count and latest checked_at.',
  grain [coverage_status, missing_reason],
  tags [jp, corp_finance, coverage, status]
);

SELECT
  coverage_status,
  missing_reason,
  COUNT(*) AS company_count,
  MAX(checked_at) AS latest_checked_at
FROM vertex_jp_corp_finance_coverage
GROUP BY coverage_status, missing_reason
