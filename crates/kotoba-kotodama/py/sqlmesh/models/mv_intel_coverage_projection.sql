-- Intel coverage projection: inferred cohort counts per target domain and status.
MODEL (
  name dev.mv_intel_coverage_projection,
  kind FULL,
  dialect postgres,
  description 'Per (target_domain, status): cohort count, estimated count, avg confidence.',
  grain [target_domain, status],
  tags [intel, coverage, cohort]
);

SELECT
  target_domain,
  status,
  COUNT(*) AS cohort_count,
  SUM(estimated_count) AS estimated_count,
  AVG(confidence) AS avg_confidence,
  MAX(created_at) AS latest_created_at
FROM vertex_intel_inferred_cohort
GROUP BY target_domain, status
