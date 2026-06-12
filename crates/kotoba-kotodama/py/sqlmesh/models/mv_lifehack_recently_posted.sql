-- Lifehack recently posted: per-tip last post timestamp and count.
MODEL (
  name dev.mv_lifehack_recently_posted,
  kind FULL,
  dialect postgres,
  description 'Per (tip_id, topic_id): last_posted_at_ms and post count from active post log.',
  grain [tip_id, topic_id],
  tags [lifehack, post, recent]
);

SELECT
  tip_id,
  topic_id,
  MAX(posted_at_ms) AS last_posted_at_ms,
  COUNT(*) AS post_count
FROM vertex_lifehack_post_log
WHERE status = 'active'
GROUP BY tip_id, topic_id
