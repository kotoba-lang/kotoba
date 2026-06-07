-- SQLMesh audit: mv_jpn_jpo_app_by_ipc invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jpo_status_known,
  model dev.mv_jpn_jpo_app_by_ipc,
  dialect postgres,
  description 'status must be one of filed/pending/granted (filtered by WHERE clause).'
);
SELECT *
FROM dev.mv_jpn_jpo_app_by_ipc
WHERE status NOT IN ('filed', 'pending', 'granted');

---

AUDIT (
  name assert_jpo_app_count_positive,
  model dev.mv_jpn_jpo_app_by_ipc,
  dialect postgres,
  description 'app_count must be > 0 (group rows imply at least one app per IPC class).'
);
SELECT *
FROM dev.mv_jpn_jpo_app_by_ipc
WHERE app_count <= 0;
