-- SQLMesh audit: mv_intel_coverage_projection invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_intel_avg_confidence_bounded,
  model dev.mv_intel_coverage_projection,
  dialect postgres,
  description 'avg_confidence must be in [0, 1] when present.'
);
SELECT *
FROM dev.mv_intel_coverage_projection
WHERE avg_confidence IS NOT NULL
  AND (avg_confidence < 0 OR avg_confidence > 1);

---

AUDIT (
  name assert_intel_cohort_count_positive,
  model dev.mv_intel_coverage_projection,
  dialect postgres,
  description 'cohort_count must be > 0 (group rows imply at least one cohort).'
);
SELECT *
FROM dev.mv_intel_coverage_projection
WHERE cohort_count <= 0;
