-- SQLMesh audit: mv_iryo_admission_count_by_dept invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_iryo_admission_subtype_le_total,
  model dev.mv_iryo_admission_count_by_dept,
  dialect postgres,
  description 'emergency + elective + transfer must not exceed admit_count (other admission_type values allowed).'
);
SELECT *
FROM dev.mv_iryo_admission_count_by_dept
WHERE emergency_count + elective_count + transfer_count > admit_count;

---

AUDIT (
  name assert_iryo_admission_count_positive,
  model dev.mv_iryo_admission_count_by_dept,
  dialect postgres,
  description 'admit_count must be > 0 (group rows imply at least one admission).'
);
SELECT *
FROM dev.mv_iryo_admission_count_by_dept
WHERE admit_count <= 0;
