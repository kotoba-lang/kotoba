-- Lifehack trending topic: per-topic post and engagement aggregates.
MODEL (
  name dev.mv_lifehack_trending_topic,
  kind FULL,
  dialect postgres,
  description 'Per topic_id: post count, total engagement, and last_posted_at_ms.',
  grain [topic_id],
  tags [lifehack, topic, trending]
);

SELECT
  topic_id,
  COUNT(*) AS post_count,
  SUM(COALESCE(engagement_score, 0)) AS engagement_total,
  MAX(posted_at_ms) AS last_posted_at_ms
FROM vertex_lifehack_post_log
WHERE status = 'active'
GROUP BY topic_id
