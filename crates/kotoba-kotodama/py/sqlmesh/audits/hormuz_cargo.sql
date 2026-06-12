-- SQLMesh audit: mv_open_hormuz_cargo_by_category invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_hormuz_cargo_volume_value_nonnegative,
  model dev.mv_open_hormuz_cargo_by_category,
  dialect postgres,
  description 'total_volume and total_value must be >= 0.'
);
SELECT *
FROM dev.mv_open_hormuz_cargo_by_category
WHERE total_volume < 0 OR total_value < 0;

---

AUDIT (
  name assert_hormuz_cargo_manifest_count_positive,
  model dev.mv_open_hormuz_cargo_by_category,
  dialect postgres,
  description 'manifest_count must be > 0 (group rows imply at least one declared manifest).'
);
SELECT *
FROM dev.mv_open_hormuz_cargo_by_category
WHERE manifest_count <= 0;
