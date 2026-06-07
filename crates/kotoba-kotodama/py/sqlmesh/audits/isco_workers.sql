-- SQLMesh audit: mv_open_isco_workers_by_occupation invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_isco_avg_confidence_bounded,
  model dev.mv_open_isco_workers_by_occupation,
  dialect postgres,
  description 'avg_confidence must be in [0, 1] when present.'
);
SELECT *
FROM dev.mv_open_isco_workers_by_occupation
WHERE avg_confidence IS NOT NULL
  AND (avg_confidence < 0 OR avg_confidence > 1);

---

AUDIT (
  name assert_isco_avg_years_nonnegative,
  model dev.mv_open_isco_workers_by_occupation,
  dialect postgres,
  description 'avg_years_experience must be >= 0 when present.'
);
SELECT *
FROM dev.mv_open_isco_workers_by_occupation
WHERE avg_years_experience IS NOT NULL
  AND avg_years_experience < 0;
