-- SQLMesh audit: mv_world_did_per_host invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_world_did_per_host_count_positive,
  model dev.mv_world_did_per_host,
  dialect postgres,
  description 'did_count must be > 0 (group rows imply at least one DID).'
);
SELECT *
FROM dev.mv_world_did_per_host
WHERE did_count <= 0;

---

AUDIT (
  name assert_world_did_per_host_app_host_present,
  model dev.mv_world_did_per_host,
  dialect postgres,
  description 'app_host must be NOT NULL after canonicalization.'
);
SELECT *
FROM dev.mv_world_did_per_host
WHERE app_host IS NULL;
