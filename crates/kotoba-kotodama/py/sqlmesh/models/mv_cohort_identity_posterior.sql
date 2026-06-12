-- Cohort identity posterior probability and fission readiness from evidence records.
MODEL (
  name dev.mv_cohort_identity_posterior,
  kind FULL,
  dialect postgres,
  description 'Per-cohort evidence count, avg/max posterior, judge agreement, and fission-ready count.',
  grain [cohort_did],
  tags [cohort, identity, posterior, fission, evidence]
);

SELECT
  cohort_did,
  COUNT(*)::BIGINT                                              AS evidence_count,
  AVG(posterior)::DOUBLE PRECISION                              AS avg_posterior,
  MAX(posterior)::DOUBLE PRECISION                              AS max_posterior,
  SUM(CASE WHEN judge_agreement THEN 1 ELSE 0 END)::BIGINT      AS judge_agree_count,
  SUM(CASE WHEN posterior > 0.95 AND judge_agreement
           THEN 1 ELSE 0 END)::BIGINT                           AS fission_ready_count,
  MAX(observed_at)                                              AS last_evidence_at
FROM vertex_repo_record
WHERE collection = 'com.etzhayyim.cohort.evidence'
GROUP BY cohort_did
