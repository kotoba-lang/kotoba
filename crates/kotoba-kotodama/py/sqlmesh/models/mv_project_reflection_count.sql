-- Project reflection count: per-convo projector reflection count.
MODEL (
  name dev.mv_project_reflection_count,
  kind FULL,
  dialect postgres,
  description 'Per convo_id: count of com.etzhayyim.projector.reflection records.',
  grain [convo_id],
  tags [project, reflection, count]
);

SELECT
  convo_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_convo
WHERE kind = 'com.etzhayyim.projector.reflection'
  AND convo_id IS NOT NULL
GROUP BY convo_id
