-- SQLMesh audit: mv_jpn_mlit_active_restrictions invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_mlit_restriction_count_positive,
  model dev.mv_jpn_mlit_active_restrictions,
  dialect postgres,
  description 'restriction_count must be > 0 (group rows imply at least one active restriction).'
);
SELECT *
FROM dev.mv_jpn_mlit_active_restrictions
WHERE restriction_count <= 0;

---

AUDIT (
  name assert_mlit_road_code_present,
  model dev.mv_jpn_mlit_active_restrictions,
  dialect postgres,
  description 'road_code must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_jpn_mlit_active_restrictions
WHERE road_code IS NULL;
