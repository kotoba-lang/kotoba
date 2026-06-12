-- Vertex seibutsu observation count: per-(actor, taxon) biological observation count.
MODEL (
  name dev.mv_vertex_seibutsu_observation_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, taxon_id): observation count from vertex_seibutsu_observation.',
  grain [actor_id, taxon_id],
  tags [seibutsu, observation, count, biology]
);

SELECT
  actor_id,
  taxon_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_seibutsu_observation
GROUP BY actor_id, taxon_id
