-- Drive recent activity: daily file activity per owner.
MODEL (
  name dev.mv_drive_recent_activity,
  kind FULL,
  dialect postgres,
  description 'Per (owner_did, activity_day): file activity count and last seq from vertex_drive_file.',
  grain [owner_did, activity_day],
  tags [drive, activity, owner, daily]
);

SELECT
  owner_did,
  SUBSTRING(COALESCE(updated_at, created_at, ''), 1, 10) AS activity_day,
  COUNT(*) AS activity_count,
  MAX(_seq) AS last_seq
FROM vertex_drive_file
WHERE owner_did IS NOT NULL
GROUP BY owner_did, SUBSTRING(COALESCE(updated_at, created_at, ''), 1, 10)
