-- Workspace activity daily: message, event, and file counts per actor per day.
MODEL (
  name dev.mv_workspace_activity_daily,
  kind FULL,
  dialect postgres,
  description 'Per (actor_did, activity_day, activity_type): activity count from workspace events.',
  grain [actor_did, activity_day, activity_type],
  tags [workspace, activity, daily]
);

WITH activity_union AS (
  SELECT actor_did, DATE(created_at) AS activity_day, 'message' AS activity_type
  FROM vertex_workspace_message
  UNION ALL
  SELECT actor_did, DATE(created_at) AS activity_day, 'event' AS activity_type
  FROM vertex_workspace_event
  UNION ALL
  SELECT actor_did, DATE(created_at) AS activity_day, 'file' AS activity_type
  FROM vertex_workspace_file
)
SELECT
  actor_did,
  activity_day,
  activity_type,
  COUNT(*) AS activity_count
FROM activity_union
GROUP BY actor_did, activity_day, activity_type
