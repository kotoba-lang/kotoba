-- Projector reflection count: reflection count per conversation.
MODEL (
  name dev.mv_projector_reflection_count,
  kind FULL,
  dialect postgres,
  description 'Per convo_id: count of projector reflections.',
  grain [convo_id],
  tags [projector, reflection, convo, count]
);

SELECT
  convo_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_projector_reflection
WHERE convo_id IS NOT NULL
GROUP BY convo_id
