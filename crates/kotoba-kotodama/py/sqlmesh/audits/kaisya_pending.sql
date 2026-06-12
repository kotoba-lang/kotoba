-- SQLMesh audit: mv_kaisya_pending_count invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_kaisya_critical_le_pending,
  model dev.mv_kaisya_pending_count,
  dialect postgres,
  description 'critical_count must not exceed pending_count.'
);
SELECT *
FROM dev.mv_kaisya_pending_count
WHERE critical_count > pending_count;

---

AUDIT (
  name assert_kaisya_pending_positive,
  model dev.mv_kaisya_pending_count,
  dialect postgres,
  description 'pending_count must be > 0 (group rows imply at least one pending task).'
);
SELECT *
FROM dev.mv_kaisya_pending_count
WHERE pending_count <= 0;
