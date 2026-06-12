-- SQLMesh audit: mv_jpn_jma_active_warnings invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jma_warning_count_positive,
  model dev.mv_jpn_jma_active_warnings,
  dialect postgres,
  description 'warning_count must be > 0 (group rows imply at least one active warning).'
);
SELECT *
FROM dev.mv_jpn_jma_active_warnings
WHERE warning_count <= 0;

---

AUDIT (
  name assert_jma_warning_type_present,
  model dev.mv_jpn_jma_active_warnings,
  dialect postgres,
  description 'warning_type must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_jpn_jma_active_warnings
WHERE warning_type IS NULL;
