-- SQLMesh audit: mv_signal_area_integral invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_signal_area_a_info_nonnegative,
  model dev.mv_signal_area_integral,
  dialect postgres,
  description 'a_info (sum of area_contrib) must be >= 0.'
);
SELECT *
FROM dev.mv_signal_area_integral
WHERE a_info < 0;

---

AUDIT (
  name assert_signal_area_coverage_grade_known,
  model dev.mv_signal_area_integral,
  dialect postgres,
  description 'coverage_grade must be one of BELOW_BASELINE / PARTIAL / OPTIMAL.'
);
SELECT *
FROM dev.mv_signal_area_integral
WHERE coverage_grade NOT IN ('BELOW_BASELINE', 'PARTIAL', 'OPTIMAL');
