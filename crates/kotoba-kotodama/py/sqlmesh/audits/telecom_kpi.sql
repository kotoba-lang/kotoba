-- SQLMesh audit: mv_telecom_kpi_breach_rate invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_kpi_breach_le_sample,
  model dev.mv_telecom_kpi_breach_rate,
  dialect postgres,
  description 'breach_count must not exceed sample_count.'
);
SELECT *
FROM dev.mv_telecom_kpi_breach_rate
WHERE breach_count > sample_count;

---

AUDIT (
  name assert_telecom_kpi_counts_nonnegative,
  model dev.mv_telecom_kpi_breach_rate,
  dialect postgres,
  description 'sample_count and breach_count must be >= 0.'
);
SELECT *
FROM dev.mv_telecom_kpi_breach_rate
WHERE sample_count < 0 OR breach_count < 0;
