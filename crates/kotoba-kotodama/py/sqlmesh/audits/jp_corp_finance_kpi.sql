-- SQLMesh audit: mv_jp_corp_finance_process_kpi invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_corp_finance_kpi_outcome_le_total,
  model dev.mv_jp_corp_finance_process_kpi,
  dialect postgres,
  description 'success_count + error_count must not exceed exec_count (other status values allowed).'
);
SELECT *
FROM dev.mv_jp_corp_finance_process_kpi
WHERE success_count + error_count > exec_count;

---

AUDIT (
  name assert_jp_corp_finance_kpi_duration_ordered,
  model dev.mv_jp_corp_finance_process_kpi,
  dialect postgres,
  description 'avg_duration_ms must not exceed max_duration_ms (when both non-null).'
);
SELECT *
FROM dev.mv_jp_corp_finance_process_kpi
WHERE avg_duration_ms IS NOT NULL
  AND max_duration_ms IS NOT NULL
  AND avg_duration_ms > max_duration_ms;
