-- SQLMesh audit: mv_open_kev_remediation_lag invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_kev_entry_count_positive,
  model dev.mv_open_kev_remediation_lag,
  dialect postgres,
  description 'entry_count must be > 0 (group rows imply at least one active KEV entry).'
);
SELECT *
FROM dev.mv_open_kev_remediation_lag
WHERE entry_count <= 0;

---

AUDIT (
  name assert_kev_exploitation_maturity_present,
  model dev.mv_open_kev_remediation_lag,
  dialect postgres,
  description 'exploitation_maturity must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_open_kev_remediation_lag
WHERE exploitation_maturity IS NULL;
