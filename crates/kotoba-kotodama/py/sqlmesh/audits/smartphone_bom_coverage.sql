-- SQLMesh audit: mv_open_smartphone_bom_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_smartphone_bom_open_le_total,
  model dev.mv_open_smartphone_bom_coverage,
  dialect postgres,
  description 'open_lines must not exceed total_lines.'
);
SELECT *
FROM dev.mv_open_smartphone_bom_coverage
WHERE open_lines > total_lines;

---

AUDIT (
  name assert_smartphone_bom_open_score_bounded,
  model dev.mv_open_smartphone_bom_coverage,
  dialect postgres,
  description 'open_score_pct must be in [0, 100] (computed from open_lines/total_lines).'
);
SELECT *
FROM dev.mv_open_smartphone_bom_coverage
WHERE open_score_pct < 0 OR open_score_pct > 100;
