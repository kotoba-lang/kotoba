-- Recent active or archived chat conversations projection.
MODEL (
  name dev.mv_chat_recent_conversations,
  kind FULL,
  dialect postgres,
  description 'Active and archived chat conversations from vertex_chat_conversation.',
  grain [conv_id],
  tags [chat, conversation, recent, active]
);

SELECT
  owner_did,
  conv_id,
  title,
  agent_did,
  model_hint,
  message_count,
  last_message_at,
  status,
  created_at
FROM vertex_chat_conversation
WHERE status IN ('active', 'archived')
