-- SQLMesh audit: mv_open_opec_member_compliance invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_opec_compliance_pct_bounded,
  model dev.mv_open_opec_member_compliance,
  dialect postgres,
  description 'avg_compliance must be in [0, 100] (compliance is a percentage).'
);
SELECT *
FROM dev.mv_open_opec_member_compliance
WHERE avg_compliance < 0 OR avg_compliance > 100;

---

AUDIT (
  name assert_opec_report_count_positive,
  model dev.mv_open_opec_member_compliance,
  dialect postgres,
  description 'report_count must be > 0 (group rows imply at least one published report).'
);
SELECT *
FROM dev.mv_open_opec_member_compliance
WHERE report_count <= 0;
