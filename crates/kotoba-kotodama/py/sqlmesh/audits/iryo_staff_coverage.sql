-- SQLMesh audit: mv_iryo_staff_coverage_gap invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_iryo_staff_gap_consistent,
  model dev.mv_iryo_staff_coverage_gap,
  dialect postgres,
  description 'gap must equal required_total - rostered_total.'
);
SELECT *
FROM dev.mv_iryo_staff_coverage_gap
WHERE gap <> required_total - rostered_total;

---

AUDIT (
  name assert_iryo_staff_required_nonnegative,
  model dev.mv_iryo_staff_coverage_gap,
  dialect postgres,
  description 'required_total and rostered_total must be >= 0.'
);
SELECT *
FROM dev.mv_iryo_staff_coverage_gap
WHERE required_total < 0 OR rostered_total < 0;
