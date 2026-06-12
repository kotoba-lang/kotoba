-- SQLMesh audit: mv_open_smartphone_layer_kpi invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_smartphone_layer_outcomes_le_exec,
  model dev.mv_open_smartphone_layer_kpi,
  dialect postgres,
  description 'success_count + error_count must not exceed exec_count.'
);
SELECT *
FROM dev.mv_open_smartphone_layer_kpi
WHERE success_count + error_count > exec_count;

---

AUDIT (
  name assert_smartphone_layer_duration_ordered,
  model dev.mv_open_smartphone_layer_kpi,
  dialect postgres,
  description 'avg_duration_ms must not exceed max_duration_ms.'
);
SELECT *
FROM dev.mv_open_smartphone_layer_kpi
WHERE avg_duration_ms IS NOT NULL
  AND max_duration_ms IS NOT NULL
  AND avg_duration_ms > max_duration_ms;
