-- Vertex shigotoba company profile count: per-actor company profile count.
MODEL (
  name dev.mv_vertex_shigotoba_company_profile_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: company profile count from vertex_shigotoba_company_profile.',
  grain [actor_id],
  tags [shigotoba, company_profile, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_shigotoba_company_profile
GROUP BY actor_id
