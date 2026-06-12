-- Active chat conversations with message count in the last 24 hours.
MODEL (
  name dev.mv_chat_active_24h,
  kind FULL,
  dialect postgres,
  description 'Active conversations with message count in last 24h via to_timestamp(ts_ms/1000.0).',
  grain [owner_did, conv_id],
  tags [chat, active, 24h, messages, realtime]
);

SELECT
  c.owner_did,
  c.conv_id,
  c.title,
  COUNT(m.vertex_id) AS msg_count_24h,
  MAX(m.ts_ms) AS last_msg_ts_ms
FROM vertex_chat_conversation c
JOIN vertex_chat_message m ON m.conv_id = c.conv_id
WHERE c.status = 'active'
  AND m.status = 'active'
  AND to_timestamp(m.ts_ms / 1000.0) > now() - INTERVAL '24 hours'
GROUP BY c.owner_did, c.conv_id, c.title
