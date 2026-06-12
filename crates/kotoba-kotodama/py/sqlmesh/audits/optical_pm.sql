-- SQLMesh audit: mv_telecom_optical_pm_summary invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_optical_pm_value_ordered,
  model dev.mv_telecom_optical_pm_summary,
  dialect postgres,
  description 'min_value <= avg_value <= max_value.'
);
SELECT *
FROM dev.mv_telecom_optical_pm_summary
WHERE min_value > avg_value
   OR avg_value > max_value;

---

AUDIT (
  name assert_optical_pm_event_count_positive,
  model dev.mv_telecom_optical_pm_summary,
  dialect postgres,
  description 'event_count must be > 0 (group rows imply at least one event).'
);
SELECT *
FROM dev.mv_telecom_optical_pm_summary
WHERE event_count <= 0;
