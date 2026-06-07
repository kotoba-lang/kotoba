-- Workspace action queue: per-owner unread/upcoming/stale workspace counts.
MODEL (
  name dev.mv_workspace_action_queue,
  kind FULL,
  dialect postgres,
  description 'Per owner_did: unread message count, upcoming event count, stale thread count via 3 CTE FULL OUTER JOIN.',
  grain [owner_did],
  tags [workspace, action_queue, owner]
);

WITH unread AS (
  SELECT owner_did, COUNT(*) AS unread_message_count
  FROM vertex_workspace_message
  WHERE owner_did IS NOT NULL
    AND COALESCE(is_read, FALSE) = FALSE
  GROUP BY owner_did
),
upcoming AS (
  SELECT owner_did, COUNT(*) AS upcoming_event_count
  FROM vertex_workspace_event
  WHERE owner_did IS NOT NULL
    AND SUBSTRING(COALESCE(start_at, ''), 1, 10) >= SUBSTRING(CAST(NOW() AS VARCHAR), 1, 10)
  GROUP BY owner_did
),
stale_threads AS (
  SELECT owner_did, COUNT(*) AS stale_thread_count
  FROM vertex_workspace_thread
  WHERE owner_did IS NOT NULL
    AND SUBSTRING(COALESCE(last_message_at, ''), 1, 10) <= SUBSTRING(CAST(NOW() AS VARCHAR), 1, 10)
  GROUP BY owner_did
)
SELECT
  unread.owner_did,
  COALESCE(unread.unread_message_count, 0) AS unread_message_count,
  COALESCE(upcoming.upcoming_event_count, 0) AS upcoming_event_count,
  COALESCE(stale_threads.stale_thread_count, 0) AS stale_thread_count
FROM unread
FULL OUTER JOIN upcoming ON unread.owner_did = upcoming.owner_did
FULL OUTER JOIN stale_threads ON COALESCE(unread.owner_did, upcoming.owner_did) = stale_threads.owner_did
