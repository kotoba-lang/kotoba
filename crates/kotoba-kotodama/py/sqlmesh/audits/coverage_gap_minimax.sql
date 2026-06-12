-- SQLMesh audit: mv_coverage_gap_minimax correctness checks.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_coverage_gap_minimax_no_defer,
  model dev.mv_coverage_gap_minimax,
  dialect postgres,
  description 'recipe_kind=defer must never appear in mv_coverage_gap_minimax (filtered by WHERE clause).'
);
SELECT *
FROM dev.mv_coverage_gap_minimax
WHERE recipe_kind = 'defer';

---

AUDIT (
  name assert_coverage_gap_minimax_regret_nonnegative,
  model dev.mv_coverage_gap_minimax,
  dialect postgres,
  description 'Regret must be >= 0 for all rows (world_total >= 0, coverage_rate in [0,1]).'
);
SELECT *
FROM dev.mv_coverage_gap_minimax
WHERE regret < 0;
