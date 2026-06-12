-- Fukkou politician activity: action counts per politician.
MODEL (
  name dev.mv_fukkou_politician_activity,
  kind FULL,
  dialect postgres,
  description 'Per (politician_vid, action): action count from edge_fukkou_politician_acted.',
  grain [politician_vid, action],
  tags [fukkou, politician, activity]
);

SELECT
  src_vid AS politician_vid,
  action,
  COUNT(*) AS action_count
FROM edge_fukkou_politician_acted
GROUP BY src_vid, action
