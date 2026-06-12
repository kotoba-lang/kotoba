-- SQLMesh audit: mv_open_seiyaku_released_batches invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_seiyaku_status_known,
  model dev.mv_open_seiyaku_released_batches,
  dialect postgres,
  description 'status must be released or amended (filtered by WHERE clause).'
);
SELECT *
FROM dev.mv_open_seiyaku_released_batches
WHERE status NOT IN ('released', 'amended');

---

AUDIT (
  name assert_seiyaku_released_at_present,
  model dev.mv_open_seiyaku_released_batches,
  dialect postgres,
  description 'released_at must be NOT NULL (released batches have a release timestamp).'
);
SELECT *
FROM dev.mv_open_seiyaku_released_batches
WHERE released_at IS NULL;
