-- SQLMesh audit: mv_telecom_call_volume invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_call_duration_nonnegative,
  model dev.mv_telecom_call_volume,
  dialect postgres,
  description 'total_duration_seconds must be >= 0.'
);
SELECT *
FROM dev.mv_telecom_call_volume
WHERE total_duration_seconds < 0;

---

AUDIT (
  name assert_telecom_call_count_positive,
  model dev.mv_telecom_call_volume,
  dialect postgres,
  description 'call_count must be > 0 (group rows imply at least one voice call).'
);
SELECT *
FROM dev.mv_telecom_call_volume
WHERE call_count <= 0;
