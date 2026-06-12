-- SQLMesh audit: mv_telecom_li_warrant_state invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_li_warrant_count_positive,
  model dev.mv_telecom_li_warrant_state,
  dialect postgres,
  description 'warrant_count must be > 0 (group rows imply at least one warrant).'
);
SELECT *
FROM dev.mv_telecom_li_warrant_state
WHERE warrant_count <= 0;

---

AUDIT (
  name assert_telecom_li_jurisdiction_present,
  model dev.mv_telecom_li_warrant_state,
  dialect postgres,
  description 'jurisdiction must be NOT NULL (grain field, lawful intercept needs jurisdiction).'
);
SELECT *
FROM dev.mv_telecom_li_warrant_state
WHERE jurisdiction IS NULL;
