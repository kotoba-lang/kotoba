-- Shinshi model activity: chat message and scene counts per model.
MODEL (
  name dev.mv_shinshi_model_activity,
  kind FULL,
  dialect postgres,
  description 'Per model_did: char name, series, distinct chat message count, and scene count.',
  grain [model_did],
  tags [shinshi, model, activity, chat, scene]
);

SELECT
  p.model_did,
  MAX(p.char_name) AS char_name,
  MAX(p.series) AS series,
  COUNT(DISTINCT c.vertex_id) AS chat_messages,
  COUNT(DISTINCT s.vertex_id) AS scenes
FROM vertex_shinshi_model_profile p
LEFT JOIN vertex_shinshi_chat_message c ON c.model_did = p.model_did
LEFT JOIN vertex_shinshi_scene s ON s.model_did = p.model_did
GROUP BY p.model_did
