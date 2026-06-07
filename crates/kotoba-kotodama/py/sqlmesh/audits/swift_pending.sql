-- SQLMesh audit: mv_open_swift_pending_messages invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_swift_pending_count_positive,
  model dev.mv_open_swift_pending_messages,
  dialect postgres,
  description 'pending_count must be > 0 (group rows imply at least one pending/submitted message).'
);
SELECT *
FROM dev.mv_open_swift_pending_messages
WHERE pending_count <= 0;

---

AUDIT (
  name assert_swift_pending_amount_nonnegative,
  model dev.mv_open_swift_pending_messages,
  dialect postgres,
  description 'pending_amount_sum must be >= 0 (SWIFT amounts are non-negative).'
);
SELECT *
FROM dev.mv_open_swift_pending_messages
WHERE pending_amount_sum < 0;
