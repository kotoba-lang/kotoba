-- SQLMesh audit: mv_open_gas_open_leaks invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_gas_leak_count_positive,
  model dev.mv_open_gas_open_leaks,
  dialect postgres,
  description 'open_leak_count must be > 0 (group rows imply at least one open leak).'
);
SELECT *
FROM dev.mv_open_gas_open_leaks
WHERE open_leak_count <= 0;

---

AUDIT (
  name assert_gas_segment_present,
  model dev.mv_open_gas_open_leaks,
  dialect postgres,
  description 'segment_vertex_id must be NOT NULL (grain field).'
);
SELECT *
FROM dev.mv_open_gas_open_leaks
WHERE segment_vertex_id IS NULL;
