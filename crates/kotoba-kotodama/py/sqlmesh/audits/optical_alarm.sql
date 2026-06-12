-- SQLMesh audit: mv_telecom_optical_alarm_state invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_optical_alarm_count_positive,
  model dev.mv_telecom_optical_alarm_state,
  dialect postgres,
  description 'alarm_count must be > 0 (group rows imply at least one alarm).'
);
SELECT *
FROM dev.mv_telecom_optical_alarm_state
WHERE alarm_count <= 0;

---

AUDIT (
  name assert_optical_alarm_severity_present,
  model dev.mv_telecom_optical_alarm_state,
  dialect postgres,
  description 'severity must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_telecom_optical_alarm_state
WHERE severity IS NULL;
