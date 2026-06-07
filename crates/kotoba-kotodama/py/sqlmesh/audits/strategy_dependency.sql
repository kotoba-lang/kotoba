-- SQLMesh audit: mv_strategy_dependency_degree invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_strategy_dependency_counts_nonnegative,
  model dev.mv_strategy_dependency_degree,
  dialect postgres,
  description 'dependency_count and dependent_count must be >= 0.'
);
SELECT *
FROM dev.mv_strategy_dependency_degree
WHERE dependency_count < 0 OR dependent_count < 0;

---

AUDIT (
  name assert_strategy_dependency_scope_strategy,
  model dev.mv_strategy_dependency_degree,
  dialect postgres,
  description 'graph_scope is hard-coded to "strategy"; should never be anything else.'
);
SELECT *
FROM dev.mv_strategy_dependency_degree
WHERE graph_scope <> 'strategy';
