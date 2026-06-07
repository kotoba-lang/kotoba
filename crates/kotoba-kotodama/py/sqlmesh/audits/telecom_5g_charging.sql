-- SQLMesh audit: mv_telecom_5g_charging_summary invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_5g_charging_amounts_nonnegative,
  model dev.mv_telecom_5g_charging_summary,
  dialect postgres,
  description 'total_amount and total_units must be >= 0.'
);
SELECT *
FROM dev.mv_telecom_5g_charging_summary
WHERE total_amount < 0 OR total_units < 0;

---

AUDIT (
  name assert_telecom_5g_charging_record_count_positive,
  model dev.mv_telecom_5g_charging_summary,
  dialect postgres,
  description 'record_count must be > 0 (group rows imply at least one charging record).'
);
SELECT *
FROM dev.mv_telecom_5g_charging_summary
WHERE record_count <= 0;
