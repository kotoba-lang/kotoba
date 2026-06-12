-- Cohort k-drift: distinct signal kinds and evidence count proxy for signal diversity.
MODEL (
  name dev.mv_cohort_k_drift,
  kind FULL,
  dialect postgres,
  description 'Per-cohort distinct signal kinds and k_proxy (evidence count / signal kinds) from cohort evidence.',
  grain [cohort_did],
  tags [cohort, k_drift, signal, diversity, evidence]
);

SELECT
  cohort_did,
  COUNT(DISTINCT signal_kind)::BIGINT AS distinct_signal_kinds,
  COUNT(*)::BIGINT                    AS evidence_count,
  CASE WHEN COUNT(DISTINCT signal_kind) = 0 THEN 0
       ELSE COUNT(*) / COUNT(DISTINCT signal_kind)
  END::BIGINT                         AS k_proxy
FROM vertex_repo_record
WHERE collection = 'com.etzhayyim.cohort.evidence'
GROUP BY cohort_did
