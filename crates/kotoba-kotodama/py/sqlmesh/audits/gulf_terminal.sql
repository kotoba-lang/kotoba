-- SQLMesh audit: mv_open_gulf_terminal_throughput invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_gulf_terminal_total_tonnes_nonnegative,
  model dev.mv_open_gulf_terminal_throughput,
  dialect postgres,
  description 'total_tonnes must be >= 0 (loading volumes are non-negative).'
);
SELECT *
FROM dev.mv_open_gulf_terminal_throughput
WHERE total_tonnes < 0;

---

AUDIT (
  name assert_gulf_terminal_loading_count_positive,
  model dev.mv_open_gulf_terminal_throughput,
  dialect postgres,
  description 'loading_count must be > 0 (group rows imply at least one completed loading).'
);
SELECT *
FROM dev.mv_open_gulf_terminal_throughput
WHERE loading_count <= 0;
