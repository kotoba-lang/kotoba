-- Kaisya pending count: pending task count per human DID with critical and timing aggregates.
MODEL (
  name dev.mv_kaisya_pending_count,
  kind FULL,
  dialect postgres,
  description 'Per human_did: pending task count, critical count (priority=1), earliest due, and latest task creation.',
  grain [human_did],
  tags [kaisya, task, pending]
);

SELECT
  human_did,
  COUNT(*) AS pending_count,
  COUNT(*) FILTER (WHERE priority = 1) AS critical_count,
  MIN(due_at) AS earliest_due_at,
  MAX(created_at) AS latest_task_at
FROM vertex_kaisya_task
WHERE status = 'pending'
GROUP BY human_did
