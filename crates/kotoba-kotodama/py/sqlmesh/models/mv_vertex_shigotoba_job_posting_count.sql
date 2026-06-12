-- Vertex shigotoba job posting count: per-(actor, source) job posting count.
MODEL (
  name dev.mv_vertex_shigotoba_job_posting_count,
  kind FULL,
  dialect postgres,
  description 'Per (actor_id, source): job posting count from vertex_shigotoba_job_posting.',
  grain [actor_id, source],
  tags [shigotoba, job_posting, count]
);

SELECT
  actor_id,
  source,
  COUNT(*)::BIGINT AS cnt
FROM vertex_shigotoba_job_posting
GROUP BY actor_id, source
