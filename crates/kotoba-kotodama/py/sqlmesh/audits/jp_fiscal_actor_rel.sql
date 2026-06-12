-- SQLMesh audit: mv_jp_fiscal_actor_relationship_degree invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_actor_distinct_le_outbound,
  model dev.mv_jp_fiscal_actor_relationship_degree,
  dialect postgres,
  description 'distinct_object_count must not exceed outbound_count.'
);
SELECT *
FROM dev.mv_jp_fiscal_actor_relationship_degree
WHERE distinct_object_count > outbound_count;

---

AUDIT (
  name assert_jp_fiscal_actor_outbound_positive,
  model dev.mv_jp_fiscal_actor_relationship_degree,
  dialect postgres,
  description 'outbound_count must be > 0 (group rows imply at least one edge).'
);
SELECT *
FROM dev.mv_jp_fiscal_actor_relationship_degree
WHERE outbound_count <= 0;
