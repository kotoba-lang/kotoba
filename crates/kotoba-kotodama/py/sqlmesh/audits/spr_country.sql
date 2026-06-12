-- SQLMesh audit: mv_open_spr_by_country invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_spr_pct_full_bounded,
  model dev.mv_open_spr_by_country,
  dialect postgres,
  description 'avg_pct_full must be in [0, 100] (SPR fill percentage).'
);
SELECT *
FROM dev.mv_open_spr_by_country
WHERE avg_pct_full < 0 OR avg_pct_full > 100;

---

AUDIT (
  name assert_spr_coverage_days_nonnegative,
  model dev.mv_open_spr_by_country,
  dialect postgres,
  description 'avg_coverage_days must be >= 0 (days cannot be negative).'
);
SELECT *
FROM dev.mv_open_spr_by_country
WHERE avg_coverage_days < 0;
