-- SQLMesh audit: mv_oil_coverage_live invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_oil_coverage_rate_bounded,
  model dev.mv_oil_coverage_live,
  dialect postgres,
  description 'coverage_rate must be in [0, 1] (defaults to 0 when target_count = 0).'
);
SELECT *
FROM dev.mv_oil_coverage_live
WHERE coverage_rate < 0 OR coverage_rate > 1;

---

AUDIT (
  name assert_oil_coverage_gap_nonnegative,
  model dev.mv_oil_coverage_live,
  dialect postgres,
  description 'coverage_gap must be >= 0 (uses GREATEST(target - actual, 0)).'
);
SELECT *
FROM dev.mv_oil_coverage_live
WHERE coverage_gap < 0;
