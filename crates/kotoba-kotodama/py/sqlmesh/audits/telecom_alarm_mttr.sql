-- SQLMesh audit: mv_telecom_alarm_mttr invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_alarm_mttr_ordered,
  model dev.mv_telecom_alarm_mttr,
  dialect postgres,
  description 'min_mttr <= avg_mttr <= max_mttr.'
);
SELECT *
FROM dev.mv_telecom_alarm_mttr
WHERE min_mttr_seconds > avg_mttr_seconds
   OR avg_mttr_seconds > max_mttr_seconds;

---

AUDIT (
  name assert_telecom_alarm_mttr_nonnegative,
  model dev.mv_telecom_alarm_mttr,
  dialect postgres,
  description 'mttr_seconds and cleared_count must be >= 0.'
);
SELECT *
FROM dev.mv_telecom_alarm_mttr
WHERE min_mttr_seconds < 0
   OR max_mttr_seconds < 0
   OR avg_mttr_seconds < 0
   OR cleared_count < 0;
