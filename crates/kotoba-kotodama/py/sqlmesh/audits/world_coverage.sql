-- SQLMesh audit: mv_world_coverage_live invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_world_coverage_rate_bounded,
  model dev.mv_world_coverage_live,
  dialect postgres,
  description 'coverage_rate must be in [0, 1] when world_total > 0; otherwise NULL is acceptable.'
);
SELECT *
FROM dev.mv_world_coverage_live
WHERE coverage_rate IS NOT NULL
  AND (coverage_rate < 0 OR coverage_rate > 1);

---

AUDIT (
  name assert_world_coverage_collected_consistent,
  model dev.mv_world_coverage_live,
  dialect postgres,
  description 'collected = GREATEST(did_count, record_count, vertex_count); none can exceed collected.'
);
SELECT *
FROM dev.mv_world_coverage_live
WHERE did_count > collected
   OR record_count > collected
   OR vertex_count > collected;
