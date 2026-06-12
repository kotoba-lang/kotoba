-- Projector message convo activity: per-convo message count and latest timestamp.
MODEL (
  name dev.mv_projector_message_convo_activity,
  kind FULL,
  dialect postgres,
  description 'Per convo_id: message count and latest_ts_ms from vertex_projector_message.',
  grain [convo_id],
  tags [projector, message, convo, activity]
);

SELECT
  convo_id,
  COUNT(*) AS message_count,
  MAX(ts_ms) AS latest_ts_ms
FROM vertex_projector_message
GROUP BY convo_id
