-- SQLMesh audit: mv_open_navy_advisory_active invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_navy_advisory_warning_count_positive,
  model dev.mv_open_navy_advisory_active,
  dialect postgres,
  description 'warning_count must be > 0 (group rows imply at least one active warning).'
);
SELECT *
FROM dev.mv_open_navy_advisory_active
WHERE warning_count <= 0;

---

AUDIT (
  name assert_navy_advisory_authority_present,
  model dev.mv_open_navy_advisory_active,
  dialect postgres,
  description 'authority must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_open_navy_advisory_active
WHERE authority IS NULL;
