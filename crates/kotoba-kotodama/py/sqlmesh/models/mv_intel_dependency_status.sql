-- Intel dependency status: edge count and avg confidence per predicate and status.
MODEL (
  name dev.mv_intel_dependency_status,
  kind FULL,
  dialect postgres,
  description 'Per (predicate, status): dependency edge count and average confidence.',
  grain [predicate, status],
  tags [intel, dependency, confidence, status]
);

SELECT
  predicate,
  status,
  COUNT(*) AS edge_count,
  AVG(confidence) AS avg_confidence
FROM edge_intel_dependency
GROUP BY predicate, status
